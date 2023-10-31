import hashlib
import socket
from dataclasses import dataclass


@dataclass
class Peer:
	friendly_name: str
	service_name: str
	fqdn: str
	uuid: str
	ipv4_addresses: list[str]
	ipv6_addresses: list[str]
	addresses: list[str]
	versions: list[int]
	version: int = None
	generator = None
	shared_key = bytes()
	ready = False
	we_ready = False
	connection: socket.socket = None
	data_address: tuple() = None
	data_connection: socket.socket = None

	def secure_hash(self) -> bytes:
		hashable_contents = []
		hashable_contents.append(self.friendly_name)
		hashable_contents.append(str(self.uuid))
		hashable_contents.extend([str(version) for version in self.versions])
		return hashlib.sha3_256("".join(hashable_contents).encode()).digest()

peer_list: list[Peer] = []
