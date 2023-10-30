import os
import pathlib
import threading
from Crypto.Cipher import ChaCha20_Poly1305
from Crypto.Random import get_random_bytes
from time import sleep

import storage_backing

from storage_metadata import load_metadata, write_metadata
from read_coded import ReadCoded
from simplenc import BinaryCoder
from enum import Enum, auto
from constants import *
from peer import *

# ASCII unit separator control character
SEP = "\x1f"

DEBUG = False

reads: dict[str, ReadCoded] = {}


class Command(Enum):
	PAIR = auto()
	CONNECT = auto()
	KEY = auto()
	SYNC = auto()
	READY = auto()
	DISCONNECT = auto()
	CREATE = auto()
	RENAME = auto()
	LIST = auto()
	READ = auto()
	DATA = auto()
	STATS = auto()
	WRITE = auto()
	REMOVE = auto()


def pton(path: str) -> pathlib.PurePosixPath:
	return pathlib.PurePosixPath("/", str(path).replace("\\", "/"))


def ntop(path: str, mount = True) -> str:
	path = path.removeprefix("/")
	if os.name == "nt":
		path = path.replace("/", "\\")
	return str(pathlib.Path(MOUNT_POINT if mount else "", path))


def identify_peer(address: str, timeout: int = 10):
    if address.startswith("::ffff:"):
        address = address.removeprefix("::ffff:")
    while 0 < timeout:
        for peer in peer_list:
            if address in peer.addresses:
                return peer
        sleep(1)
        timeout -= 1


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

	def join(self, timeout: float | None = None):
		threading.Thread.join(self, timeout)
		return self._return


def thread(function):
	def run(*args, **kwargs):
		thread = ThreadWithReturnValue(target=function, args=args, kwargs=kwargs)
		thread.start()
		return thread
	return run


@thread
def transmit(peer: Peer, command: Command, path: pathlib.PurePosixPath = None, payload = None, **kwargs):
	# processing what to send
	output = "".encode()
	match command:
		case command.PAIR:
			output = f"{Command.PAIR.value}:{SEP.join([str(version) for version in SUPPORTED_VERSIONS])}\n".encode()
		case command.CONNECT:
			output = f"{Command.CONNECT.value}:{SEP.join([str(version) for version in SUPPORTED_VERSIONS])}\n".encode()
		case command.KEY:
			output = f"{Command.KEY.value}:{payload.decode()}\n".encode()
		case command.SYNC:
			output = f"{Command.SYNC.value}:\n".encode()
		case command.READY:
			output = f"{Command.READY.value}:\n".encode()
		case command.DISCONNECT:
			output = f"{Command.DISCONNECT.value}:\n".encode()
		case Command.CREATE:
			seed = kwargs["seed"]
			output = f"{Command.CREATE.value}:{path}{SEP}{payload}{SEP}{seed}\n".encode()
		case Command.RENAME:
			output = f"{Command.RENAME.value}:{path}{SEP}{payload}\n".encode()
		case Command.LIST:
			output = f"{Command.LIST.value}:{path}\n".encode()
		case Command.READ:
			payload: BinaryCoder
			skip = kwargs["skip"]
			equations = kwargs["equations"]
			reads[str(path)] = ReadCoded()
			reads[str(path)].data = bytearray(payload.num_symbols)
			reads[str(path)].decoder = payload
			output = Command.READ.value.to_bytes(1, "big") + f"{path}{SEP}{skip}{SEP}{equations}\n".encode()
		case Command.STATS:
			output = f"{Command.STATS.value}:{path}\n".encode()
		case Command.REMOVE:
			output = f"{Command.REMOVE.value}:{path}\n".encode()
	# transmission
	if command == Command.READ:
		"""Send a read request for a file over UDP"""
		peer.data_connection.sendto(output, peer.data_address)
	else:
		while peer.connection == None:
			sleep(0.001)
		peer.connection.sendall(output)
	# receipt and processing
	match command:
		case Command.PAIR:
			data = peer.connection.recv(1500)
			data = int.from_bytes(data, "big")
			return data == 1
		case Command.CONNECT:
			data = peer.connection.recv(1500)
			data = int.from_bytes(data, "big")
			return data
		case Command.KEY:
			return peer.connection.recv(1500)
		case Command.SYNC:
			data = peer.connection.recv(1500)
			data = int.from_bytes(data, "big")
			return data == 1
		case Command.READY:
			data = peer.connection.recv(1500)
			data = int.from_bytes(data, "big")
			return data == 1
		case Command.DISCONNECT:
			peer.connection.shutdown(socket.SHUT_WR)
		case Command.LIST:
			data = peer.connection.recv(1500)
			data = data.decode().removesuffix("\n")
			folders, files = data.split(":")
			folders = folders.split(SEP)
			files = files.split(SEP)
			folders = [folder for folder in folders if folder != ""]
			files = [file for file in files if file != ""]
			return folders, files
		case Command.STATS:
			data = peer.connection.recv(1500)
			data = data.decode().removesuffix("\n")
			size, ctime, mtime, atime = data.split(SEP)
			size = int(size)
			ctime = int(ctime)
			mtime = int(mtime)
			atime = int(atime)
			return size, ctime, mtime, atime


@thread
def transmit_data(peer: Peer, command: Command, path: pathlib.PurePosixPath | str, payload = None, **kwargs):
	"""Send a file, e.g. a write command, with network-coding and transmit over UDP"""
	seed: int = kwargs["seed"]
	payload: bytes
	packets = 1
	# encryption, XChaCha20-Poly1305 https://pycryptodome.readthedocs.io/en/latest/src/cipher/chacha20_poly1305.html
	cipher = ChaCha20_Poly1305.new(key=peer.shared_key[-32:], nonce=get_random_bytes(24))
	cipher.update(str(path).encode())
	ciphertext, tag = cipher.encrypt_and_digest(payload)
	payload_length = len(ciphertext)
	# encoding
	# TODO: split data into packet sizes
	# TODO: divide data into n + 1 peer's worth of equations, distribute to n peers
	encoder = BinaryCoder(packets, payload_length * 8, 1)
	coefficient = [0] * encoder.num_symbols
	coefficient[0] = 1
	bits = []
	for byte in ciphertext:
		bits.extend([byte >> i & 1 for i in range(8 - 1, -1, -1)])
	encoder.consume_packet(coefficient, bits)
	# fetching encoded data and confirming sufficiently decodes
	coefficient, packet = encoder.get_sys_coded_packet(0)
	packet = "".join(map(str, packet))
	packet = [int(packet[i:i+8], 2) for i in range(0, len(packet), 8)]
	coefficient = int("".join(map(str, coefficient)), 2)
	output = command.value.to_bytes(1, "big")
	output += str(path).encode()
	output += SEP.encode()
	output += seed.to_bytes(8, "big")
	output += payload_length.to_bytes(8, "big")
	output += cipher.nonce  # 24 bytes
	output += coefficient.to_bytes(2, "big")
	output += len(bytes(packet)).to_bytes(2, "big")
	output += bytes(packet)
	output += tag  # 16 bytes
	output += "\n".encode()
	# transmission
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
			if os.name == "nt":
				file = os.path.join(path, file)
			if os.name == "posix":
				file = path + "/" + file
			if DEBUG: print("creating local file:", file)
			seed = create_local(file, False)
			if DEBUG: print("requesting remote file:", file)
			length, ctime, mtime, atime = stats(file)
			if DEBUG: print(file, "size is", length, "bytes")
			contents, seed = read(file, BinaryCoder(length, 8, seed), length * 2)
			metadata = load_metadata(file)
			metadata.seed = seed
			write_metadata(file, metadata)
			write_local(file, 0, length, contents)
			time_local(file, ctime, mtime, atime)
		else:
			if DEBUG: print(file, "is in both, comparing times")
			length, ctime, mtime, atime = stats(file)
			_, _, local_mtime, _ = stats_local(file)
			if DEBUG: print(local_mtime, mtime)
			if local_mtime < mtime:
				# remote version is more recent, we should fetch it
				if DEBUG: print("fetching more recent remote file:", file)
				metadata = load_metadata(file)
				contents, seed = read(file, BinaryCoder(length, 8, metadata.seed), length * 2)
				write_local(file, 0, len(contents), contents)
				time_local(file, ctime, mtime, atime)
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
	return True


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


def stats(path: str):
	path = pton(path)
	if DEBUG: print(f"requesting stats of {path}")
	for peer in peer_list:
		return transmit(peer, Command.STATS, path).join()


def create(path: str, directory: bool, seed: int):
	path = pton(path)
	if DEBUG: print(f"creating {path} ({'folder' if directory else 'file'})")
	for peer in peer_list:
		transmit(peer, Command.CREATE, path, "1" if directory else "0", seed=seed)


def read(path: str, decoder: BinaryCoder, length: int) -> bytes:
	path = pton(path)
	if DEBUG: print(f"reading {path} ({length})")
	for peer in peer_list:
		transmit(peer, Command.READ, path, decoder, skip=0, equations=length)
	# TODO: switch to events rather than polling?
	if str(path) not in reads:
		return bytes()
	timeout = 10
	# TODO: keep requesting until decoded
	while not reads[str(path)].decoder.is_fully_decoded():
		sleep(0.001)
		timeout -= 0.001
		if timeout < 0:
			return bytes(), reads[str(path)].decoder.seed
	for i in range(reads[str(path)].decoder.num_symbols):
		if reads[str(path)].decoder.is_symbol_decoded(i):
			symbol = reads[str(path)].decoder.get_decoded_symbol(i)
			if type(reads[str(path)].data) == bytearray:
				reads[str(path)].data[i:i+1] = int("".join(map(str, symbol)), 2).to_bytes(1, "big")
	contents = bytes(reads[str(path)].data)
	# del reads[str(path)]
	return contents, reads[str(path)].decoder.seed


def rename(path: str, new_path: str):
	path = pton(path)
	new_path = pton(new_path)
	if DEBUG: print(f"renaming {path} -> {new_path}")
	for peer in peer_list:
		transmit(peer, Command.RENAME, path, new_path)


def write(path: str, seed: int, data: bytes):
	path = pton(path)
	data = data.replace("\r\n".encode(), "\n".encode())
	length = len(data)
	if DEBUG: print(f"writing  {path} ({length}): {data}")
	for peer in peer_list:
		transmit_data(peer, Command.WRITE, path, data, seed=seed, skip=0)


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


def stats_local(path: str):
	if os.name == "nt":
		path = ntop(path, False)
	if DEBUG: print(f"sizing local {path}")
	return storage_backing.stats(path)


def time_local(path: str, ctime: int, mtime: int, atime: int):
	if os.name == "nt":
		path = ntop(path, False)
	if DEBUG: print(f"setting local time {path} to {atime}, {mtime}")
	return storage_backing.time(path, ctime, mtime, atime)


def create_local(path: str, directory: bool, seed: int = None):
	if os.name == "nt":
		path = ntop(path, False)
	if DEBUG: print(f"creating local {path} ({'folder' if directory else 'file'})")
	if os.name == "posix":
		return storage_backing.create(path, directory, seed)[1]
	if os.name == "nt":
		return storage_backing.create(path, directory, seed)

def read_local(path: str, skip: int, equations: int) -> bytes:
	if os.name == "nt":
		path = ntop(path, False)
	if DEBUG: print(f"reading local {path} ({equations} equations)")
	return storage_backing.read_file(path, skip, equations)


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
