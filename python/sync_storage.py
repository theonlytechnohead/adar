
import pathlib
import threading

from enum import Enum, auto
from peers import *


DEBUG = True


class Command(Enum):
	CREATE = auto()
	READ = auto()
	RENAME = auto()
	WRITE = auto()
	REMOVE = auto()


def treat_path(path: str) -> pathlib.PurePosixPath:
	return "/" / pathlib.PurePosixPath(path.replace("\\", "/"))


def thread(function):
    def run(*args, **kwargs):
        t = threading.Thread(target=function, args=args, kwargs=kwargs)
        t.start()
        return t
    return run


@thread
def transmit(peer: Peer, command: Command, path: str, payload = None, **kwargs):
	output = "".encode()
	match command:
		case Command.CREATE:
			directory = kwargs["directory"]
			pass
		case Command.READ:
			length = kwargs["length"]
			pass
		case Command.RENAME:
			pass
		case Command.WRITE:
			start = kwargs["start"]
			length = kwargs["length"]
			pass
		case Command.REMOVE:
			pass
	peer.connection.sendall(output)
	if command == Command.READ:
		return peer.connection.recv()


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
