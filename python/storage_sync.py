import os
import pathlib
import threading

import storage_backing

from enum import Enum, auto
from constants import *
from peers import *

# ASCII unit separator control character
SEP = "\x1f"

DEBUG = False


class Command(Enum):
	CREATE = auto()
	READ = auto()
	RENAME = auto()
	WRITE = auto()
	REMOVE = auto()


def pton(path: str) -> pathlib.PurePosixPath:
	return pathlib.PurePosixPath("/", path.replace("\\", "/"))


def ntop(path: str, mount = True) -> pathlib.Path:
	return pathlib.Path(MOUNT_POINT if mount else "", path.removeprefix("/").replace("/", os.sep))


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
			output = f"{Command.CREATE}:{path}{SEP}{payload}\n".encode()
		case Command.READ:
			length = kwargs["length"]
			output = f"{Command.READ}:{path}{SEP}{payload}{SEP}{length}\n".encode()
		case Command.RENAME:
			output = f"{Command.RENAME}:{path}{SEP}{payload}\n".encode()
		case Command.WRITE:
			start = kwargs["start"]
			length = kwargs["length"]
			output = f"{Command.WRITE}:{path}{SEP}{start}{SEP}{length}{SEP}{payload.decode()}\n".encode()
		case Command.REMOVE:
			output = f"{Command.REMOVE}:{path}\n".encode()
	with socket.create_connection((peer.fqdn, PORT)) as connection:
		connection.sendall(output)
	if command == Command.READ:
		return 0, bytes()


def create(path: str, directory: bool):
	path = pton(path)
	if DEBUG: print(f"creating {path} ({'folder' if directory else 'file'})")
	for peer in peer_list:
		transmit(peer, Command.CREATE, path, directory)


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
		transmit(peer, Command.WRITE, path, data, start=start, length=length)


def remove(path: str):
	path = pton(path)
	if DEBUG: print(f"removing {path}")
	for peer in peer_list:
		transmit(peer, Command.REMOVE, path)


def create_local(path: str, directory: bool):
	if DEBUG: print(f"creating local {path} ({'folder' if directory else 'file'})")
	storage_backing.create(ntop(path, False), directory)


def read_local(path: str, start: int, length: int) -> bytes:
	if DEBUG: print(f"reading local {path} ({start}->{start+length})")
	return storage_backing.read(ntop(path, False), start, length)


def rename_local(path: str, new_path: str):
	if DEBUG: print(f"renaming local {path} -> {new_path}")
	storage_backing.rename(ntop(path, False), ntop(new_path, False))


def write_local(path: str, start: int, length: int, data: bytes):
	if DEBUG: print(f"writing local: {path} ({start}->{start+length}): {data}")
	storage_backing.write(ntop(path, False), ntop(path), start, length, data)


def remove_local(path: str):
	if DEBUG: print(f"removing local: {path}")
	storage_backing.remove(ntop(path, False))	
