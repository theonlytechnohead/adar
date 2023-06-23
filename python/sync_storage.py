import os
import pathlib
import shutil
import threading

import storage_backing

from enum import Enum, auto
from constants import *
from peers import *

SEP = "\x1f"

DEBUG = True


class Command(Enum):
	CREATE = auto()
	READ = auto()
	RENAME = auto()
	WRITE = auto()
	REMOVE = auto()


def treat_path(path: str) -> pathlib.PurePosixPath:
	return pathlib.PurePosixPath("/", path.replace("\\", "/"))


def untreat_path(path: str, mount = True) -> pathlib.Path:
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
		pass


def create(path: str, directory: bool):
	path = treat_path(path)
	if DEBUG: print(f"creating {path} ({'folder' if directory else 'file'})")
	for peer in peer_list:
		transmit(peer, Command.CREATE, path, directory)


def read(path: str, start: int, length: int) -> bytes:
	path = treat_path(path)
	if DEBUG: print(f"reading {path} ({start}->{start+length})")
	output = bytearray(length)
	for peer in peer_list:
		index, byte = transmit(peer, Command.READ, path, start, length=length)
		output[index:index + 1] = byte
	return bytes(output)


def rename(path: str, new_path: str):
	path = treat_path(path)
	new_path = treat_path(new_path)
	if DEBUG: print(f"renaming {path} -> {new_path}")
	for peer in peer_list:
		transmit(peer, Command.RENAME, path, new_path)


def write(path: str, start: int, data: bytes):
	path = treat_path(path)
	data = data.replace("\r\n".encode(), "\n".encode())
	length = len(data)
	if DEBUG: print(f"writing  {path} ({start}->{start+length}): {data}")
	for peer in peer_list:
		transmit(peer, Command.WRITE, path, data, start=start, length=length)


def remove(path: str):
	path = treat_path(path)
	if DEBUG: print(f"removing {path}")
	for peer in peer_list:
		transmit(peer, Command.REMOVE, path)


def create_local(path: str, directory: bool):
	if DEBUG: print(f"creating local {path} ({'folder' if directory else 'file'})")
	storage_backing.create(untreat_path(path, False), directory)


def read_local(path: str, start: int, length: int) -> bytes:
	if DEBUG: print(f"reading local {path} ({start}->{start+length})")
	return storage_backing.read(untreat_path(path, False), start, length)


def rename_local(path: str, new_path: str):
	if DEBUG: print(f"renaming local {path} -> {new_path}")
	storage_backing.rename(untreat_path(path, False), untreat_path(new_path, False))


def write_local(path: str, start: int, length: int, data: bytes):
	if DEBUG: print(f"writing local: {path} ({start}->{start+length}: {data})")
	storage_backing.write(untreat_path(path, False), start, length, data)
	path = untreat_path(path)
	with open(path, "wb") as file:
		file.seek(start)
		file.write(data)


def remove_local(path: str):
	if DEBUG: print(f"removing local: {path}")
	backing_path = untreat_path(path, False)
	storage_backing.remove(backing_path)	
