import os
import random
import shutil
from win32_setctime import setctime

from simplenc import BinaryCoder

from constants import *
from storage_metadata import *

def ls(path: str):
	if os.name == "posix":
		if not path.startswith("/"):
			path = "/" + path
		path = ROOT_POINT + path
		listing = os.listdir(path)
		files = [f for f in listing if os.path.isfile(os.path.join(path, f))]
		folders = [f for f in listing if os.path.isdir(os.path.join(path, f))]
		return folders, files
	if os.name == "nt":
		root_path = os.path.join(ROOT_POINTS[0], path)
		listing = os.listdir(root_path)
		files = [f for f in listing if os.path.isfile(os.path.join(root_path, f))]
		folders = [f for f in listing if os.path.isdir(os.path.join(root_path, f))]
		return folders, files


def stats(path: str):
	if os.name == "posix":
		if not path.startswith("/"):
			path = "/" + path
		path = ROOT_POINT + path
		stats = os.stat(path)
		# TODO: use separate storage to get ctime
		return stats.st_size, stats.st_ctime_ns, stats.st_mtime_ns, stats.st_atime_ns
	if os.name == "nt":
		metadata = load_metadata(path)
		return metadata.length, metadata.ctime_ns, metadata.mtime_ns, metadata.atime_ns


def time(path: str, ctime: int, mtime: int, atime: int):
	if os.name == "posix":
		if not path.startswith("/"):
			path = "/" + path
		root_path = ROOT_POINT + path
		os.utime(root_path, times=None, ns=(atime, mtime))
		# TODO: use separate storage to set ctime
		mount_path = MOUNT_POINT + path
		os.utime(mount_path, times=None, ns=(atime, mtime))
	if os.name == "nt":
		ctime = ctime / 1_000_000_000  # convert ns to s
		for root in ROOT_POINTS:
			root_path = os.path.join(root, path)
			os.utime(root_path, times=None, ns=(atime, mtime))
			setctime(root_path, ctime)
		mount_path = os.path.join(MOUNT_POINT, path)
		os.utime(mount_path, times=None, ns=(atime, mtime))
		setctime(mount_path, ctime)
		# TODO: update metadata file


def create(path: str, directory: bool, **kwargs):
	if os.name == "posix":
		if not path.startswith("/"):
			path = "/" + path
		path = ROOT_POINT + path
		mode = kwargs["mode"] if "mode" in kwargs else None
		if directory:
			if mode:
				return os.mkdir(path, mode)
			else:
				return os.mkdir(path)
		else:
			# TODO: use separate storage to set ctime
			if mode:
				return os.open(path, os.O_WRONLY | os.O_CREAT, mode)
			else:
				return os.open(path, os.O_WRONLY | os.O_CREAT)
	if os.name == "nt":
		for root in ROOT_POINTS:
			root_path = os.path.join(root, path)
			if directory:
				os.mkdir(root_path)
			else:
				open(root_path, "x").close()
		if not directory:
			load_metadata(path)
		else:
			os.mkdir(os.path.join(METADATA_DIRECTORY, path))


def read_file(path: str, start: int, length: int, **kwargs) -> bytes:
	if os.name == "posix":
		if "handle" in kwargs:
			handle = kwargs["handle"]
			os.lseek(handle, start, os.SEEK_SET)
			return os.read(handle, length)
		else:
			if not path.startswith("/"):
				path = "/" + path
			path = ROOT_POINT + path
			output = bytes()
			with open(path, "rb") as file:
				file.seek(start)
				output = file.read(length)
			return output
	if os.name == "nt":
		metadata = load_metadata(path)
		metadata.update_atime()
		output = bytearray(length)
		with open(os.path.join(COEFFICIENT_DIRECTORY, path), "rb") as file:
			seed = file.read()
		with open(os.path.join(SYMBOL_DIRECTORY, path), "rb") as file:
			symbols = file.read()
		seed = int.from_bytes(seed, "big")
		symbols = list(symbols)
		decoder = BinaryCoder(length, 8, seed)
		for symbol in symbols:
			coefficient, _ = decoder.generate_coefficients()
			symbol = [symbol >> i & 1 for i in range(8 - 1, -1, -1)]
			decoder.consume_packet(coefficient, symbol)
		for i in range(length):
			if decoder.is_symbol_decoded(i):
				symbol = decoder.get_decoded_symbol(i)
				output[i:i+1] = int("".join(map(str, symbol)), 2).to_bytes(1, "big")
		return bytes(output)


def rename(path: str, new_path: str):
	if os.name == "posix":
		if not path.startswith("/"):
			path = "/" + path
		path = ROOT_POINT + path
		new_path = ROOT_POINT + new_path
		return os.rename(path, new_path)
	if os.name == "nt":
		for root in ROOT_POINTS:
			root_path = os.path.join(root, path)
			root_new_path = os.path.join(root, new_path)
			try:
				os.rename(root_path, root_new_path)
			except FileExistsError:
				# something went wrong, it's probably not our fault though - ignore
				return
		try:
			os.rename(os.path.join(METADATA_DIRECTORY, path), os.path.join(METADATA_DIRECTORY, new_path))
			os.rename(os.path.join(COEFFICIENT_DIRECTORY, path), os.path.join(COEFFICIENT_DIRECTORY, new_path))
			os.rename(os.path.join(SYMBOL_DIRECTORY, path), os.path.join(SYMBOL_DIRECTORY, new_path))
		except:
			pass  # it's probably a directory


def write(path: str, start: int, length: int, data: bytes, **kwargs):
	if os.name == "posix":
		# TODO: implement network coding
		if "handle" in kwargs.keys():
			handle = kwargs["handle"]
			os.lseek(handle, start, os.SEEK_SET)
			return os.write(handle, data)
		else:
			if not path.startswith("/"):
				path = "/" + path
			path = ROOT_POINT + path
			with open(path, "wb") as file:
				file.write(data)
	if os.name == "nt":
		metadata = load_metadata(path)
		metadata.length = length
		metadata.update_mtime()
		metadata.update_atime()
		seed = random.randint(0, 65535)
		encoder = BinaryCoder(length, 8, seed)
		for i in range(length):
			coefficients = [0] * length
			coefficients[i] = 1
			byte = data[i]
			encoder.consume_packet(coefficients, [byte >> i & 1 for i in range(8 - 1, -1, -1)])
		symbols = []
		for _ in range(length * 2):
			symbol = encoder.get_generated_coded_packet()
			symbol = int("".join(map(str, symbol)), 2)
			symbols.append(symbol)
		seed = seed.to_bytes(2, "big")
		symbols = bytes(symbols)
		with open(os.path.join(COEFFICIENT_DIRECTORY, path), "wb") as file:
			file.write(seed)
		with open(os.path.join(SYMBOL_DIRECTORY, path), "wb") as file:
			file.write(symbols)
		write_metadata(path, metadata)


def remove_path(path: str):
	if os.name == "posix":
		# TODO
		pass
	if os.name == "nt":
		if os.path.exists(path):
			if os.path.isdir(path):
				shutil.rmtree(path)
			else:
				os.remove(path)


def remove(path: str):
	if os.name == "posix":
		if not path.startswith("/"):
			path = "/" + path
		path = ROOT_POINT + path
		if os.path.isdir(path):
			return os.rmdir(path)
		else:
			return os.unlink(path)
	if os.name == "nt":
		# TODO: figure out why directories are sticky (sometimes?)
		for root in ROOT_POINTS:
			root_path = os.path.join(root, path)
			remove_path(root_path)
		remove_path(os.path.join(METADATA_DIRECTORY, path))
		remove_path(os.path.join(COEFFICIENT_DIRECTORY, path))
		remove_path(os.path.join(SYMBOL_DIRECTORY, path))
		
