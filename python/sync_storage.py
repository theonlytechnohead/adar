
import pathlib
import threading

from enum import Enum, auto
from peers import *
from time import sleep

SEP = "\x1f"

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
			output = f"{Command.WRITE}:{path}{SEP}{start}{SEP}{length}{SEP}{payload}".encode()
		case Command.REMOVE:
			output = f"{Command.REMOVE}:{path}\n".encode()
	peer.connection.sendall(output)
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
