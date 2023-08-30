import os
import pathlib
import threading

import storage_backing

from simplenc import BinaryCoder
from enum import Enum, auto
from constants import *
from peer import *

# ASCII unit separator control character
SEP = "\x1f"

DEBUG = True


class Command(Enum):
	CREATE = auto()
	READ = auto()
	DATA = auto()
	RENAME = auto()
	WRITE = auto()
	REMOVE = auto()


def pton(path: str) -> pathlib.PurePosixPath:
	return pathlib.PurePosixPath("/", path.replace("\\", "/"))


def ntop(path: str, mount = True) -> str:
	path = path.removeprefix("/")
	if os.name == "nt":
		path = path.replace("/", "\\")
	return str(pathlib.Path(MOUNT_POINT if mount else "", path))


def thread(function):
    def run(*args, **kwargs):
        t = threading.Thread(target=function, args=args, kwargs=kwargs)
        t.start()
        return t
    return run


@thread
def transmit(peer: Peer, command: Command, path: pathlib.PurePosixPath, payload = None, **kwargs):
	output = "".encode()
	match command:
		case Command.CREATE:
			output = f"{Command.CREATE.value}:{path}{SEP}{payload}\n".encode()
		case Command.READ:
			"""Send a read request for a file over UDP"""
			length = kwargs["length"]
			output = f"{Command.READ.value}:{path}{SEP}{payload}{SEP}{length}\n".encode()
		case Command.RENAME:
			output = f"{Command.RENAME.value}:{path}{SEP}{payload}\n".encode()
		case Command.REMOVE:
			output = f"{Command.REMOVE.value}:{path}\n".encode()
	if command == Command.READ:
		peer.data_connection.sendto(output, peer.data_address)
	else:
		peer.connection.sendall(output)
	if command == Command.READ:
		try:
			data, server = peer.data_connection.recvfrom(2048)
		except TimeoutError:
			pass
		return 0, bytes()


@thread
def transmit_data(peer: Peer, command: Command, path: pathlib.PurePosixPath | str, payload = None, **kwargs):
	"""Send a file, e.g. a write command, with network-coding and transmit over UDP"""
	start = kwargs["start"]
	length = kwargs["length"]
	payload: bytes
	encoder = BinaryCoder(length, 8, 1)
	decoder = BinaryCoder(length, 8, 1)
	for i, byte in enumerate(payload):
		coefficient = [0] * len(payload)
		coefficient[i] = 1
		bits = [byte >> i & 1 for i in range(8 - 1, -1, -1)]
		encoder.consume_packet(coefficient, bits)
	cata = bytearray()
	data = bytearray()
	while not decoder.is_fully_decoded():
		coefficient, packet = encoder.get_new_coded_packet()
		decoder.consume_packet(coefficient, packet)
		coefficient = int("".join(map(str, coefficient)), 2)
		packet = int("".join(map(str, packet)), 2)
		cata.extend((coefficient,))
		data.extend((packet,))
	cata = bytes(cata)
	data = bytes(data)
	output = f"{command.value}:{path}{SEP}{start}{SEP}{length}{SEP}{cata.decode()}{SEP}{data.decode()}\n".encode()
	peer.data_connection.sendto(output, peer.data_address)


def create(path: str, directory: bool):
	path = pton(path)
	if DEBUG: print(f"creating {path} ({'folder' if directory else 'file'})")
	for peer in peer_list:
		transmit(peer, Command.CREATE, path, "1" if directory else "0")


def read(path: str, start: int, length: int) -> bytes:
	path = pton(path)
	if DEBUG: print(f"reading {path} ({start}->{start+length})")
	output = bytearray(length)
	for peer in peer_list:
		index, byte = transmit(peer, Command.READ, path, start, length=length)
		output[index:index + 1] = byte
	return bytes(output)


def rename(path: str, new_path: str):
	path = pton(path)
	new_path = pton(new_path)
	if DEBUG: print(f"renaming {path} -> {new_path}")
	for peer in peer_list:
		transmit(peer, Command.RENAME, path, new_path)


def write(path: str, start: int, data: bytes):
	path = pton(path)
	data = data.replace("\r\n".encode(), "\n".encode())
	length = len(data)
	if DEBUG: print(f"writing  {path} ({start}->{start+length}): {data}")
	for peer in peer_list:
		transmit_data(peer, Command.WRITE, path, data, start=start, length=length)


def remove(path: str):
	path = pton(path)
	if DEBUG: print(f"removing {path}")
	for peer in peer_list:
		transmit(peer, Command.REMOVE, path)


def create_local(path: str, directory: bool):
	if os.name == "nt":
		path = ntop(path, False)
	if DEBUG: print(f"creating local {path} ({'folder' if directory else 'file'})")
	storage_backing.create(path, directory)


def read_local(path: str, start: int, length: int) -> bytes:
	if os.name == "nt":
		path = ntop(path, False)
	if DEBUG: print(f"reading local {path} ({start}->{start+length})")
	return storage_backing.read_file(path, start, length)


def rename_local(path: str, new_path: str):
	if os.name == "nt":
		path = ntop(path, False)
		new_path = ntop(new_path, False)
	if DEBUG: print(f"renaming local {path} -> {new_path}")
	storage_backing.rename(path, new_path)


def write_local(path: str, start: int, length: int, data: bytes):
	if os.name == "posix":
		real_path = path
	if os.name == "nt":
		path = ntop(path, False)
		real_path = ntop(path)
	if DEBUG: print(f"writing local: {path} ({start}->{start+length}): {data}")
	storage_backing.write(path, start, length, data, real_path=real_path)


def remove_local(path: str):
	if os.name == "nt":
		path = ntop(path, False)
	if DEBUG: print(f"removing local: {path}")
	storage_backing.remove(path)	
