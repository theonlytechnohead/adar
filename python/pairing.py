import base64
import os
import socket
from diffiehellman import DiffieHellman
from zeroconf import ServiceInfo, IPVersion

from constants import PORT
from peer import *


def add_peer(info: ServiceInfo) -> Peer:
    peer = Peer(
        info.name,
        info.server,
        info.properties[b"uuid"].decode(),
        info.parsed_addresses(IPVersion.V4Only),
        info.parsed_addresses(IPVersion.V6Only),
        info.parsed_addresses()
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
    print(f"\tconnecting to {address}")
    connection = socket.create_connection((address, PORT))
    print(f"\tconnected to {connection.getpeername()[0]}")
    if connection.getpeername()[0] not in peer.addresses:
        connection.shutdown(socket.SHUT_RDWR)
        connection.close()
        return
    peer.connection = connection
    connection.sendall(bytes("pair?" + "\n", "utf-8"))
    received = str(connection.recv(1024), "utf-8")
    return True if received == "sure" else False


def store_peer(peer: Peer):
    if check_pair(peer):
        return
    with open("pairings", "a") as file:
        file.write(f"{peer.uuid}")
        if peer.shared_key != b"":
            file.write(f":{base64.b64encode(peer.shared_key)}")
        file.write("\n")


def pair(name: str, peer: Peer) -> bool:
    confirm = input(f"Do you want to pair with {name}? [Y/n] ")
    if confirm.lower() == "y" or confirm == "":
        if request_pair(peer):
            print("Pairing accepted")
            store_peer(peer)
            return True
        else:
            print("Pairing failed")
    return False


def connect(peer: Peer):
    if peer.generator == None:
        peer.generator = DiffieHellman(group=14, key_bits=1024)
    if peer.connection:
        print(f"\tconnected to {peer.connection.getpeername()[0]}")
    else:
        address = peer.fqdn.removesuffix(".") if peer.fqdn.endswith(".") else peer.fqdn
        print(f"\tconnecting to {address}")
        connection = socket.create_connection((address, PORT))
        print(f"\tconnected to {connection.getpeername()[0]}")
        if connection.getpeername()[0] not in peer.addresses:
            connection.shutdown(socket.SHUT_RDWR)
            connection.close()
            return
        peer.connection = connection
    our_key = peer.generator.get_public_key()
    data = "key?".encode() + base64.b64encode(our_key) + "\n".encode()
    peer.connection.sendall(data)
    data = peer.connection.recv(len(data))
    other_key = base64.b64decode(data[4:-1])
    peer.shared_key = peer.generator.generate_shared_key(other_key)
    store_peer(peer)
