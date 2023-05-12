import base64
import os
import socket
from diffiehellman import DiffieHellman
from zeroconf import ServiceInfo, IPVersion

from constants import PORT
from peers import *


def check_service(info: ServiceInfo) -> tuple[str, socket.AddressFamily]:
    v6 = info.parsed_addresses(IPVersion.V6Only)
    v4 = info.parsed_addresses(IPVersion.V4Only)
    for address in v6:
        if socket.getaddrinfo(address, PORT, socket.AF_INET6):
            return address, socket.AF_INET6
    for address in v4:
        if socket.getaddrinfo(address, PORT, socket.AF_INET):
            return v4[0], socket.AF_INET


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


def pair(name: str, info: ServiceInfo):
    confirm = input(f"Do you want to pair with {name}? [Y/n] ")
    if confirm.lower() == "y" or confirm == "":
        if request_pair(info):
            print("Pairing accepted")
            store_pair(info)
        else:
            print("Pairing failed")


def connect(info: ServiceInfo) -> tuple[str, socket.socket]:
    print(f"initiating connection")
    # fetch address to connect to
    address, mode = check_service(info)
    # initiate connection
    connection = socket.socket(mode, socket.SOCK_STREAM)
    connection.connect((address, PORT))
    print(f"connecting: {address}")
    # generate a public key to share
    generators[address] = DiffieHellman(group=14, key_bits=1024)
    our_key = generators[address].get_public_key()
    print(f"generated public key: {our_key[:10]}")
    # send a key request message along with our key
    data = "key?".encode() + base64.b64encode(our_key) + "\n".encode()
    connection.sendall(data)
    print(f"sent: {data[:10]}")
    # length of received data should be 4 + 1024 + 1 = 1029
    data = connection.recv(len(data))
    print(f"recieved: {data[:10]}")
    other_key = base64.b64decode(data[4:-1])
    print(f"received other key: {other_key[:10]}")
    # generate the shared key
    shared_key = generators[address].generate_shared_key(other_key)
    print(f"computed shared key: {shared_key[:10]}")
    keys[address] = shared_key
    print(f"connected! {address}")
    return address, connection


if __name__ == "__main__":
    # automatically generate two key pairs
    dh1 = DiffieHellman(group=14, key_bits=540)
    dh2 = DiffieHellman(group=14, key_bits=540)

    # get both public keys
    dh1_public = dh1.get_public_key()
    dh2_public = dh2.get_public_key()

    # generate shared key based on the other side's public key
    dh1_shared = dh1.generate_shared_key(dh2_public)
    dh2_shared = dh2.generate_shared_key(dh1_public)

    # the shared keys should be equal
    assert dh1_shared == dh2_shared

    print(f"{base64.b64encode(dh1_shared).decode()}")
    print(f"{base64.b64encode(dh2_shared).decode()}")
