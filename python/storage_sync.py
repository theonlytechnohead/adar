import os
import pathlib
import threading
from time import sleep

import storage_backing

from simplenc import BinaryCoder
from enum import Enum, auto
from constants import *
from peer import *

# ASCII unit separator control character
SEP = "\x1f"

DEBUG = False

reads = {}


class Command(Enum):
	PAIR = auto()
	CONNECT = auto()
	SYNC = auto()
	READY = auto()
	DISCONNECT = auto()
	CREATE = auto()
	RENAME = auto()
	LIST = auto()
	READ = auto()
	DATA = auto()
	SIZE = auto()
	WRITE = auto()
	REMOVE = auto()


def pton(path: str) -> pathlib.PurePosixPath:
	return pathlib.PurePosixPath("/", path.replace("\\", "/"))


def ntop(path: str, mount = True) -> str:
	path = path.removeprefix("/")
	if os.name == "nt":
		path = path.replace("/", "\\")
	return str(pathlib.Path(MOUNT_POINT if mount else "", path))


# How to get the return value from a thread? https://stackoverflow.com/a/6894023
class ThreadWithReturnValue(threading.Thread):
	def __init__(self, group=None, target=None, name=None, args=(), kwargs={}):
		threading.Thread.__init__(self, group, target, name, args, kwargs)
		self._target = target
		self._args = args
		self._kwargs = kwargs
		self._return = None

	def run(self):
		self._return = self._target(*self._args, **self._kwargs)

	def join(self):
		threading.Thread.join(self)
		return self._return


def thread(function):
	def run(*args, **kwargs):
		thread = ThreadWithReturnValue(target=function, args=args, kwargs=kwargs)
		thread.start()
		return thread
	return run


@thread
def transmit(peer: Peer, command: Command, path: pathlib.PurePosixPath = None, payload = None, **kwargs):
	output = "".encode()
	match command:
		case command.PAIR:
			output = f"pair?\n".encode()
		case command.CONNECT:
			output = f"key?{payload}\n".encode()
		case command.SYNC:
			output = f"sync?\n".encode()
		case command.READY:
			output = f"ready\n".encode()
		case command.DISCONNECT:
			output = f"bye\n".encode()
		case Command.CREATE:
			output = f"{Command.CREATE.value}:{path}{SEP}{payload}\n".encode()
		case Command.RENAME:
			output = f"{Command.RENAME.value}:{path}{SEP}{payload}\n".encode()
		case Command.LIST:
			output = f"{Command.LIST.value}:{path}\n".encode()
		case Command.READ:
			length = kwargs["length"]
			reads[str(path)] = bytearray(length)
			output = f"{Command.READ.value}:{path}{SEP}{payload}{SEP}{length}\n".encode()
		case Command.SIZE:
			output = f"{Command.SIZE.value}:{path}\n".encode()
		case Command.REMOVE:
			output = f"{Command.REMOVE.value}:{path}\n".encode()
	if command == Command.READ:
		"""Send a read request for a file over UDP"""
		peer.data_connection.sendto(output, peer.data_address)
	else:
		while peer.connection == None:
			sleep(0.001)
		peer.connection.sendall(output)
	match command:
		case Command.PAIR:
			data = peer.connection.recv(1024)
			data = data.decode().removesuffix("\n")
			return data
		case Command.CONNECT:
			data = peer.connection.recv(len(payload))
			data = data.decode().removesuffix("\n")
			return data
		case Command.SYNC:
			data = peer.connection.recv(1024)
			data = data.decode().removesuffix("\n")
			return data == "1"
		case Command.LIST:
			data = peer.connection.recv(1024)
			data = data.decode().removesuffix("\n")
			folders, files = data.split(":")
			folders = folders.split(SEP)
			files = files.split(SEP)
			folders = [folder for folder in folders if folder != ""]
			files = [file for file in files if file != ""]
			return folders, files
		case Command.SIZE:
			data = peer.connection.recv(1024)
			data = data.decode().removesuffix("\n")
			size = int(data)
			return size


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


def explore(path: str):
	if DEBUG: print("exploring", path)
	folders, files = list(path)
	local_folders, local_files = list_local(path)
	if DEBUG: print("\tremote:\t", folders, files)
	if DEBUG: print("\tlocal:\t", local_folders, local_files)
	explorable = []
	for folder in folders:
		folder = os.path.join(path, folder)
		if os.path.basename(folder) not in local_folders:
			if DEBUG: print("creating local folder:", folder)
			create_local(folder, True)
		explorable.append(folder)
	for file in files:
		if file not in local_files:
			file = os.path.join(path, file)
			if DEBUG: print("creating local file:", file)
			create_local(file, False)
			if DEBUG: print("requesting remote file:", file)
			length = size(file)
			if DEBUG: print(file, "size is", length, "bytes")
			contents = read(file, 0, length)
			write_local(file, 0, length, contents)
	return explorable


@thread
def sync():
	"""Requests folders and files to replicate on the local backing"""
	path = ""
	exploring = [path]
	new = []
	while exploring != []:
		for n in exploring:
			got = explore(os.path.join(path, n))
			new.extend([folder for folder in got if folder not in new])
			if n in new:
				new.remove(n)
		exploring = new


def list(path: str):
	path = pton(path)
	if DEBUG: print(f"requesting listing of {path}")
	all_folders = []
	all_files = []
	for peer in peer_list:
		folders, files = transmit(peer, Command.LIST, path).join()
		all_folders.extend(folders)
		all_files.extend(files)
	return all_folders, all_files


def size(path: str):
	path = pton(path)
	if DEBUG: print(f"requesting size of {path}")
	for peer in peer_list:
		return transmit(peer, Command.SIZE, path).join()


def create(path: str, directory: bool):
	path = pton(path)
	if DEBUG: print(f"creating {path} ({'folder' if directory else 'file'})")
	for peer in peer_list:
		transmit(peer, Command.CREATE, path, "1" if directory else "0")


def read(path: str, start: int, length: int) -> bytes:
	path = pton(path)
	if DEBUG: print(f"reading {path} ({start}->{start+length})")
	for peer in peer_list:
		transmit(peer, Command.READ, path, start, length=length)
	# TODO: switch to events rather than polling?
	while type(reads[str(path)]) == bytearray:
		sleep(0.001)
	data = bytes(reads[str(path)])
	del reads[str(path)]
	return data


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


def list_local(path: str):
	if os.name == "nt":
		path = ntop(path, False)
	if DEBUG: print(f"listing local {path}")
	return storage_backing.ls(path)


def size_local(path: str):
	if os.name == "nt":
		path = ntop(path, False)
	if DEBUG: print("sizing local {path}")
	return storage_backing.size(path)


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
