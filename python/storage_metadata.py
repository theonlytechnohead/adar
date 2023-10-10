from dataclasses import dataclass
import os
import json
import jsons
import time

from constants import *

@dataclass
class Metadata:
	length: int = 0
	ctime_ns: int = time.time_ns()
	mtime_ns: int = time.time_ns()
	atime_ns: int = time.time_ns()

	def update_ctime(self, ctime_ns: int = None):
		if ctime_ns:
			self.ctime_ns = ctime_ns
		else:
			self.ctime_ns = time.time_ns()

	def update_mtime(self, mtime_ns: int = None):
		if mtime_ns:
			self.mtime_ns = mtime_ns
		else:
			self.mtime_ns = time.time_ns()

	def update_atime(self, atime_ns: int = None):
		if atime_ns:
			self.atime_ns = atime_ns
		else:
			self.atime_ns = time.time_ns()


def load_metadata(path: str) -> Metadata:
	metadata = Metadata()
	if os.path.exists(os.path.join(METADATA_DIRECTORY, path)):
		with open(os.path.join(METADATA_DIRECTORY, path), "r") as file:
			metadata = jsons.load(json.load(file), Metadata)
	else:
		write_metadata(path, metadata)
	return metadata


def write_metadata(path: str, data: Metadata):
	with open(os.path.join(METADATA_DIRECTORY, path), "w") as file:
		json.dump(jsons.dump(data, Metadata), file, indent=4)


def from_ns(time):
	return time / 1_000_000_000
