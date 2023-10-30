from dataclasses import dataclass
import os
import json
import random
import sys
import jsons
import time

from constants import *

@dataclass
class Metadata:
	length: int = 0
	seed: int = random.randint(0, sys.maxsize)
	ctime_ns: int = time.time_ns()
	mtime_ns: int = time.time_ns()
	atime_ns: int = time.time_ns()

	def __init__(self) -> None:
		self.seed = random.randint(0, sys.maxsize)

	def update_ctime(self):
		self.ctime_ns = time.time_ns()

	def update_mtime(self):
		self.mtime_ns = time.time_ns()

	def update_atime(self):
		self.atime_ns = time.time_ns()


def load_metadata(path: str) -> Metadata:
	metadata = Metadata()
	if os.name == "posix":
		if not path.startswith("/"):
			path = "/" + path
		if (os.path.exists(METADATA_DIRECTORY + path)):
			with open(METADATA_DIRECTORY + path, "r") as file:
				metadata = jsons.load(json.load(file), Metadata)
		else:
			write_metadata(path, metadata)
	if os.name == "nt":
		if os.path.exists(os.path.join(METADATA_DIRECTORY, path)):
			with open(os.path.join(METADATA_DIRECTORY, path), "r") as file:
				metadata = jsons.load(json.load(file), Metadata)
		else:
			write_metadata(path, metadata)
	return metadata


def write_metadata(path: str, data: Metadata):
	if os.name == "posix":
		with open(METADATA_DIRECTORY + path, "w") as file:
			json.dump(jsons.dump(data, Metadata), file, indent=4)
	if os.name == "nt":
		with open(os.path.join(METADATA_DIRECTORY, path), "w") as file:
			json.dump(jsons.dump(data, Metadata), file, indent=4)


def from_ns(time):
	return time / 1_000_000_000
