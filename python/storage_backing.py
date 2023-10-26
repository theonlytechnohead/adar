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
		root_path = os.path.join(METADATA_DIRECTORY, path)
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
		metadata = load_metadata(path)
		metadata.ctime_ns = ctime
		metadata.mtime_ns = mtime
		metadata.atime_ns = atime
		write_metadata(path, metadata)
		mount_path = os.path.join(MOUNT_POINT, path)
		os.utime(mount_path, times=None, ns=(atime, mtime))
		setctime(mount_path, from_ns(ctime))


def create(path: str, directory: bool, seed: int | None, **kwargs):
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
		if directory:
			os.mkdir(os.path.join(METADATA_DIRECTORY, path))
			os.mkdir(os.path.join(SYMBOL_DIRECTORY, path))
		else:
			metadata = load_metadata(path)
			if seed:
				metadata.seed = seed
				write_metadata(path, seed)
			else:
				return metadata.seed



def read_file(path: str, skip: int, equations: int, **kwargs) -> bytes:
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
		write_metadata(path, metadata)
		# TODO: fetch `equations` number of equations for the file data
		with open(os.path.join(SYMBOL_DIRECTORY, path), "rb") as file:
			symbols = file.read()
		symbols = list(symbols)
		return metadata.seed, symbols[skip:skip + equations]
		output = bytearray(metadata.length)
		decoder = BinaryCoder(metadata.length, 8, metadata.seed)
		# TODO: send the generated/read equations
		for symbol in symbols:
			coefficient, _ = decoder.generate_coefficients()
			symbol = [symbol >> i & 1 for i in range(8 - 1, -1, -1)]
			decoder.consume_packet(coefficient, symbol)
		# TODO: don't bother decoding (we shouldn't store enough to fully decode anyway)
		for i in range(metadata.length):
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
		try:
			os.rename(os.path.join(METADATA_DIRECTORY, path), os.path.join(METADATA_DIRECTORY, new_path))
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
		encoder = BinaryCoder(length, 8, metadata.seed)
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
		symbols = bytes(symbols)
		with open(os.path.join(SYMBOL_DIRECTORY, path), "wb") as file:
			file.write(symbols)
		write_metadata(path, metadata)
		return metadata.seed


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
		remove_path(os.path.join(METADATA_DIRECTORY, path))
		remove_path(os.path.join(SYMBOL_DIRECTORY, path))
		
