import os
import shutil

import fec

from constants import *

def create(path: str, directory: bool):
	for root in ROOT_POINTS:
		root_path = os.path.join(root, path)
		if directory:
			os.mkdir(root_path)
		else:
			open(root_path, "x").close()


def read_file(path: str, start: int, length: int) -> bytes:
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
	return bytes(output)


def rename(path: str, new_path: str):
	for root in ROOT_POINTS:
		root_path = os.path.join(root, path)
		root_new_path = os.path.join(root, new_path)
		os.rename(root_path, root_new_path)


def write(path: str, start: int, length: int, data: bytes):
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
	for root in ROOT_POINTS:
		root_path = os.path.join(root, path)
		if os.path.isdir(root_path):
			shutil.rmtree(root_path)
		else:
			os.remove(root_path)
