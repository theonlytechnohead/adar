import base64
import os
import socket
from diffiehellman import DiffieHellman
from zeroconf import ServiceInfo, IPVersion

import storage_sync

from constants import *
from peer import *


def add_peer(info: ServiceInfo) -> Peer:
    peer = Peer(
        info.name.removesuffix(SERVICE)[:-1],
        info.name,
        info.server,
        info.properties[b"uuid"].decode(),
        info.parsed_addresses(IPVersion.V4Only),
        info.parsed_addresses(IPVersion.V6Only),
        info.parsed_addresses(),
        [int(version) for version in info.properties[b"versions"].split(storage_sync.SEP.encode())]
        )
    peer_list.append(peer)
    return peer


def check_service(info: ServiceInfo) -> tuple[str, socket.AddressFamily]:
    v6 = info.parsed_addresses(IPVersion.V6Only)
    for address in v6:
        if socket.getaddrinfo(address, PORT, socket.AF_INET6):
            return address, socket.AF_INET6
    v4 = info.parsed_addresses(IPVersion.V4Only)
    for address in v4:
        if socket.getaddrinfo(address, PORT, socket.AF_INET):
            return address, socket.AF_INET


def check_pair(peer: Peer) -> bool:
    if os.path.exists("pairings"):
        with open("pairings") as file:
            for line in file.readlines():
                if peer.uuid in line:
                    return True
    return False


def request_pair(peer: Peer) -> bool:
    address = peer.fqdn.removesuffix(".") if peer.fqdn.endswith(".") else peer.fqdn
    print(f"\tpairing to {address}")
    connection = socket.create_connection((address, PORT))
    # TODO: use standard peer identification method
    if connection.getpeername()[0] not in peer.addresses:
        connection.shutdown(socket.SHUT_RDWR)
        connection.close()
        return
    peer.connection = connection
    # TODO: timeout
    return storage_sync.transmit(peer, storage_sync.Command.PAIR).join()


def store_peer(peer: Peer):
    if check_pair(peer):
        return
    with open("pairings", "a") as file:
        file.write(f"{peer.uuid}")
        if peer.shared_key != b"":
            file.write(f":{base64.b64encode(peer.shared_key)}")
        file.write("\n")


def pair(peer: Peer) -> bool:
    confirm = input(f"Do you want to pair with {peer.friendly_name}? [Y/n] ")
    if confirm.lower() == "y" or confirm == "":
        if request_pair(peer):
            print("\tPaired!")
            store_peer(peer)
            return True
        else:
            print("\tPairing failed")
    return False


def connect(peer: Peer):
    if peer.generator == None:
        peer.generator = DiffieHellman(group=14, key_bits=540)
    if peer.connection:
        print(f"\tconnected to {peer.connection.getpeername()[0]}")
    else:
        address = peer.fqdn.removesuffix(".")
        print(f"\tconnecting to\t{address}")
        connection = socket.create_connection((address, PORT))
        print(f"\tconnected to\t{connection.getpeername()[0]}")
        if connection.getpeername()[0] not in peer.addresses:
            connection.shutdown(socket.SHUT_RDWR)
            connection.close()
            return
        peer.connection = connection
    version = int(storage_sync.transmit(peer, storage_sync.Command.CONNECT).join())
    if version not in SUPPORTED_VERSIONS:
        return False
    peer.version = version
    our_key = peer.generator.get_public_key()
    other_key = storage_sync.transmit(peer, storage_sync.Command.KEY, None, base64.b64encode(our_key)).join()
    peer.shared_key = peer.generator.generate_shared_key(other_key)
    store_peer(peer)

    family: socket.AddressFamily
    match peer.connection.family:
        case socket.AF_INET:
            family = socket.AF_INET
        case socket.AF_INET6:
            if peer.connection.getpeername()[0].startswith("::ffff:"):
                family = socket.AF_INET
            else:
                family = socket.AF_INET6
    peer.data_connection = socket.socket(family, socket.SOCK_DGRAM)
    peer.data_connection.settimeout(1)  # seconds
    peer.data_address = (peer.connection.getpeername()[0], DATA_PORT)
    return True
