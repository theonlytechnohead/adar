import os
import shutil

from simplenc import BinaryCoder

from constants import *
from storage_metadata import *

def ensure(directory: str):
	if not os.path.exists(directory):
		os.mkdir(directory)
	if not os.path.isdir(directory):
		print(f"{directory} is not a directory, exiting...")
		sys.exit(1)


def ls(path: str):
	if os.name == "posix":
		if not path.startswith("/"):
			path = "/" + path
		path = METADATA_DIRECTORY + path
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
		metadata = load_metadata(path)
		return metadata.length, metadata.ctime_ns, metadata.mtime_ns, metadata.atime_ns
	if os.name == "nt":
		metadata = load_metadata(path)
		return metadata.length, metadata.ctime_ns, metadata.mtime_ns, metadata.atime_ns


def time(path: str, ctime: int, mtime: int, atime: int):
	if os.name == "posix":
		if not path.startswith("/"):
			path = "/" + path
		metadata = load_metadata(path)
		metadata.ctime_ns = ctime
		metadata.mtime_ns = mtime
		metadata.atime_ns = atime
		write_metadata(path, metadata)
		mount_path = MOUNT_POINT + path
		os.utime(mount_path, times=None, ns=(atime, mtime))
	if os.name == "nt":
		metadata = load_metadata(path)
		metadata.ctime_ns = ctime
		metadata.mtime_ns = mtime
		metadata.atime_ns = atime
		write_metadata(path, metadata)
		# mount_path = os.path.join(MOUNT_POINT, path)
		# os.utime(mount_path, times=None, ns=(atime, mtime))
		# setctime(mount_path, from_ns(ctime))


def create(path: str, directory: bool, seed: int = None, **kwargs):
	if os.name == "posix":
		if not path.startswith("/"):
			path = "/" + path
		metadata_path = METADATA_DIRECTORY + path
		symbol_path = SYMBOL_DIRECTORY + path
		mode = kwargs["mode"] if "mode" in kwargs else None
		if directory:
			if mode:
				os.mkdir(metadata_path, mode)
				return os.mkdir(symbol_path, mode), None
			else:
				os.mkdir(metadata_path)
				return os.mkdir(symbol_path), None
		else:
			if mode:
				fh = os.open(symbol_path, os.O_WRONLY | os.O_CREAT, mode)
			else:
				fh = os.open(symbol_path, os.O_WRONLY | os.O_CREAT)
			metadata = load_metadata(path)
			if seed:
				metadata.seed = seed
				write_metadata(path, metadata)
				return fh, None
			else:
				return fh, metadata.seed
	if os.name == "nt":
		if directory:
			os.mkdir(os.path.join(METADATA_DIRECTORY, path))
			os.mkdir(os.path.join(SYMBOL_DIRECTORY, path))
		else:
			metadata = load_metadata(path)
			if seed:
				metadata.seed = seed
				write_metadata(path, metadata)
			else:
				return metadata.seed



def read_file(path: str, skip: int, equations: int, **kwargs) -> tuple[int, list[int]]:
	if os.name == "posix":
		if not path.startswith("/"):
			path = "/" + path
		metadata = load_metadata(path)
		metadata.update_atime()
		write_metadata(path, metadata)
		with open(SYMBOL_DIRECTORY + path, "rb") as file:
			symbols = file.read()
		symbols = list(symbols)
		return metadata.seed, symbols[skip:skip + equations]
	if os.name == "nt":
		metadata = load_metadata(path)
		metadata.update_atime()
		write_metadata(path, metadata)
		with open(os.path.join(SYMBOL_DIRECTORY, path), "rb") as file:
			symbols = file.read()
		symbols = list(symbols)
		return metadata.seed, symbols[skip:skip + equations]


def rename(path: str, new_path: str):
	if os.name == "posix":
		if not path.startswith("/"):
			path = "/" + path
		os.rename(METADATA_DIRECTORY + path, METADATA_DIRECTORY + new_path)
		os.rename(SYMBOL_DIRECTORY + path, SYMBOL_DIRECTORY + new_path)
	if os.name == "nt":
		try:
			os.rename(os.path.join(METADATA_DIRECTORY, path), os.path.join(METADATA_DIRECTORY, new_path))
			os.rename(os.path.join(SYMBOL_DIRECTORY, path), os.path.join(SYMBOL_DIRECTORY, new_path))
		except:
			pass  # it's probably a directory


def write(path: str, start: int, length: int, data: bytes, **kwargs):
	if os.name == "posix":
		if not path.startswith("/"):
			path = "/" + path
		metadata = load_metadata(path)
		metadata.length = length
		metadata.update_mtime()
		metadata.update_atime()
		write_metadata(path, metadata)
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
		with open(SYMBOL_DIRECTORY + path, "wb") as file:
			result = file.write(symbols)
		return length if result == length * 2 else 0, metadata.seed
	if os.name == "nt":
		metadata = load_metadata(path)
		metadata.length = length
		metadata.update_mtime()
		metadata.update_atime()
		write_metadata(path, metadata)
		encoder = BinaryCoder(length, 8, metadata.seed)
		for i in range(length):
			coefficients = [1 if j == i else 0 for j in range(length)]
			encoder.consume_packet(coefficients, [1 if digit=='1' else 0 for digit in format(data[i], "08b")])
		symbols = [0] * (length * 2)
		for i in range(length * 2):
			symbol = encoder.get_generated_coded_packet()
			symbol = int("".join(map(str, symbol)), 2)
			symbols[i] = symbol
		symbols = bytes(symbols)
		with open(os.path.join(SYMBOL_DIRECTORY, path), "wb") as file:
			file.write(symbols)
		return metadata.seed


def remove_path(path: str):
	if os.name == "posix":
		if os.path.exists(path):
			if os.path.isdir(path):
				return os.rmdir(path)
			else:
				return os.unlink(path)
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
		remove_path(METADATA_DIRECTORY + path)
		remove_path(SYMBOL_DIRECTORY + path)
	if os.name == "nt":
		# TODO: figure out why directories are sticky (sometimes?)
		remove_path(os.path.join(METADATA_DIRECTORY, path))
		remove_path(os.path.join(SYMBOL_DIRECTORY, path))
		
