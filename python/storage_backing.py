import os
import shutil

import fec

from constants import *

def ls(path: str):
	if os.name == "posix":
		pass
	if os.name == "nt":
		root_path = os.path.join(ROOT_POINTS[0], path)
		listing = os.listdir(root_path)
		files = [f for f in listing if os.path.isfile(os.path.join(root_path, f))]
		folders = [f for f in listing if os.path.isdir(os.path.join(root_path, f))]
		return folders, files


def stats(path: str):
	if os.name == "posix":
		pass
	if os.name == "nt":
		total_size = 0
		for root in ROOT_POINTS:
			root_path = os.path.join(root, path)
			stats = os.stat(root_path)
			total_size += stats.st_size
		return total_size, stats.st_ctime_ns, stats.st_mtime_ns


def time(path: str, ctime: int, atime: int):
	if os.name == "posix":
		pass
	if os.name == "nt":
		for root in ROOT_POINTS:
			root_path = os.path.join(root, path)
			os.utime(root_path, (ctime, atime))


def create(path: str, directory: bool, **kwargs):
	if os.name == "posix":
		path = ROOT_POINT + path
		mode = kwargs["mode"] if "mode" in kwargs else None
		if directory:
			if mode:
				return os.mkdir(path, mode)
			else:
				return os.mkdir(path)
		else:
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


def read_file(path: str, start: int, length: int, **kwargs) -> bytes:
	if os.name == "posix":
		handle = kwargs["handle"]
		os.lseek(handle, start, os.SEEK_SET)
		return os.read(handle, length)
	if os.name == "nt":
		output = bytearray(length)
		read = 0
		files = []
		for root in ROOT_POINTS:
			root_path = os.path.join(root, path)
			files.append(open(root_path, "rb"))
		for index, file in enumerate(files):
			file_offset = start // len(ROOT_POINTS)
			other_offset = start % len(ROOT_POINTS)
			if other_offset == index:
				file_offset += other_offset
			file.seek(file_offset)
		while read < length:
			block1 = files[0].read(1)
			block2 = files[1].read(1)
			if block2 == b"":
				block2 = b"\x00"
			decoded1, decoded2 = fec.decode(block1, block2)
			output[read:read + 1] = decoded1
			read += 1
			if block2 != b"":
				output[read:read + 1] = decoded2
				read += 1
		for file in files:
			file.close()
		return bytes(output)[start:length]


def rename(path: str, new_path: str):
	if os.name == "posix":
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


def write(path: str, start: int, length: int, data: bytes, **kwargs):
	if os.name == "posix":
		if "handle" in kwargs.keys():
			handle = kwargs["handle"]
			os.lseek(handle, start, os.SEEK_SET)
			return os.write(handle, data)
		else:
			path = ROOT_POINT + path
			with open(path, "wb") as file:
				file.write(data)
	if os.name == "nt":
		# TODO: is this really necessary? it seems to help by fixing the file size and doing placeholdery stuff that hints the OS what's happened
		real_path = kwargs["real_path"]
		try:
			with open(real_path, "wb") as file:
				file.seek(start)
				file.write(data)
		except PermissionError:
			# we aren't allowed to read this file (yet?), just ignore it
			return
		written = 0
		files = []
		for root in ROOT_POINTS:
			root_path = os.path.join(root, path)
			file = open(root_path, "wb")
			file.seek(start // 2)
			files.append(file)
		while written < length:
			byte1 = data[written:written+1]
			written += 1
			byte2 = data[written:written+1] if written < length else b""
			written += 1
			if byte2 == b"":
				byte2 = b"\x00"
			block1, block2 = fec.encode(byte1, byte2)
			files[0].write(block1)
			if byte2 != b"\x00":
				files[1].write(block2)
		for file in files:
			file.close()


def remove(path: str):
	if os.name == "posix":
		path = ROOT_POINT + path
		if os.path.isdir(path):
			return os.rmdir(path)
		else:
			return os.unlink(path)
	if os.name == "nt":
		# TODO: figure out why directories are sticky (sometimes?)
		for root in ROOT_POINTS:
			root_path = os.path.join(root, path)
			if os.path.exists(root_path):
				if os.path.isdir(root_path):
					shutil.rmtree(root_path)
				else:
					os.remove(root_path)
