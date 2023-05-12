from dataclasses import dataclass

@dataclass
class Peer:
    service_name: str
    ipv4_addresses: list[str]
    ipv6_addresses: list[str]
    addresses: list[str]
    generator = None
    shared_key = bytes()
    connection = None

peer_list: list[Peer] = []
