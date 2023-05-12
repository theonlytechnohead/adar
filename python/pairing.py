import base64
import os
import socket
from diffiehellman import DiffieHellman
from zeroconf import ServiceInfo, IPVersion

from constants import PORT
from peers import *


def add_peer(info: ServiceInfo) -> Peer:
    peer = Peer(info.get_name(), info.parsed_addresses(IPVersion.V4Only), info.parsed_addresses(IPVersion.V6Only), info.parsed_addresses())
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


def check_pair(info: ServiceInfo) -> bool:
    if os.path.exists("pairings"):
        id = str(info.properties[b"uuid"], "utf-8")
        with open("pairings") as file:
            for line in file.readlines():
                if id in line:
                    return True
    return False


def request_pair(info: ServiceInfo) -> bool:
    accepted = False
    address, mode = check_service(info)
    with socket.socket(mode, socket.SOCK_STREAM) as sock:
        sock.connect((address, PORT))
        sock.sendall(bytes("pair?" + "\n", "utf-8"))
        received = str(sock.recv(1024), "utf-8")
        accepted = True if received == "sure" else False
    return accepted


def store_pair(info: ServiceInfo):
    with open("pairings", "a") as file:
        id = str(info.properties[b"uuid"], "utf-8")
        file.write(f"{id}\n")


def pair(name: str, info: ServiceInfo) -> bool:
    confirm = input(f"Do you want to pair with {name}? [Y/n] ")
    if confirm.lower() == "y" or confirm == "":
        if request_pair(info):
            print("Pairing accepted")
            store_pair(info)
            return True
        else:
            print("Pairing failed")
    return False


def connect(peer: Peer, info: ServiceInfo) -> tuple[str, socket.socket]:
    address, mode = check_service(info)
    if peer.generator == None:
        peer.generator = DiffieHellman(group=14, key_bits=1024)
    connection = socket.socket(mode, socket.SOCK_STREAM)
    connection.connect((address, PORT))
    our_key = peer.generator.get_public_key()
    data = "key?".encode() + base64.b64encode(our_key) + "\n".encode()
    connection.sendall(data)
    data = connection.recv(len(data))
    other_key = base64.b64decode(data[4:-1])
    peer.shared_key = peer.generator.generate_shared_key(other_key)
    peer.connection = connection
