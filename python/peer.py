import socket
from dataclasses import dataclass


@dataclass
class Peer:
    service_name: str
    fqdn: str
    uuid: str
    ipv4_addresses: list[str]
    ipv6_addresses: list[str]
    addresses: list[str]
    generator = None
    shared_key = bytes()
    ready = False
    we_ready = False
    connection: socket.socket = None
    data_address: tuple() = None
    data_connection: socket.socket = None


peer_list: list[Peer] = []
