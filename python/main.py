import ipaddress
import os
import signal
import socket
import socketserver
import threading
import uuid
from time import sleep

import netifaces
from zeroconf import (IPVersion, ServiceBrowser, ServiceInfo, ServiceListener,
                      Zeroconf)

ID = uuid.getnode()
PORT = 6780
SERVICE = "_adar._tcp.local."

stop = False


class AdarListener(ServiceListener):
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        friendlyname = name.removesuffix(f".{SERVICE}")
        print(f"Service added: {friendlyname}")
        if int(info.properties[b"uuid"]) != ID:
            pair(friendlyname, info)

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass


def get_local_non_loopback_ipv4_addresses():
    # https://stackoverflow.com/questions/39988525/find-local-non-loopback-ip-address-in-python
    for interface in netifaces.interfaces():
        if netifaces.AF_INET in netifaces.ifaddresses(interface):
            for address_info in netifaces.ifaddresses(interface)[netifaces.AF_INET]:
                address_object = ipaddress.IPv4Address(address_info["addr"])
                if not address_object.is_loopback:
                    yield address_info["addr"]


def get_local_non_loopback_ipv6_addresses():
    for interface in netifaces.interfaces():
        if netifaces.AF_INET6 in netifaces.ifaddresses(interface):
            for address_info in netifaces.ifaddresses(interface)[netifaces.AF_INET6]:
                address_object = ipaddress.IPv6Address(address_info["addr"])
                if not address_object.is_loopback:
                    yield address_info["addr"]


def zeroconf() -> Zeroconf:
    zeroconf = Zeroconf()
    properties = {
        "Description": "Network coding for automated distributed storage systems",
        "uuid": ID
    }
    fqdn = socket.getfqdn()
    hostname = socket.gethostname()
    ipv4 = list(get_local_non_loopback_ipv4_addresses())
    ipv6 = list(get_local_non_loopback_ipv6_addresses())
    print(f"{hostname} ({ID}): {fqdn} ({ipv4}, {ipv6})")
    adar_info = ServiceInfo(
        SERVICE,
        name=f"{hostname}.{SERVICE}",
        port=PORT,
        properties=properties,
        server=fqdn,
        addresses=[*ipv4, *ipv6])
    zeroconf.register_service(adar_info)
    ServiceBrowser(zeroconf, SERVICE, AdarListener())
    return zeroconf


class AdarHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        self.data = str(self.rfile.readline().strip(), "utf-8")
        if self.data == "pair?":
            self.data = b"sure"
        else:
            print(f"{self.client_address[0]}: {self.data}")
            self.data = bytes(self.data.upper(), "utf-8")
        self.wfile.write(self.data)


class dual_stack(socketserver.TCPServer):
    def server_bind(self) -> None:
        self.socket = socket.create_server(
            self.server_address, family=socket.AF_INET6, dualstack_ipv6=True)


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
    if check_pair(info):
        return
    confirm = input(f"Do you want to pair with {name}? [Y/n] ")
    if confirm.lower() == "y" or confirm == "":
        if request_pair(info):
            print("Pairing accepted")
            store_pair(info)
        else:
            print("Pairing failed")


def handle(signum, frame):
    global stop
    print("Stopping...", end="")
    service.close()
    adar.shutdown()
    stop = True


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle)
    signal.signal(signal.SIGTERM, handle)
    service = zeroconf()
    adar = dual_stack(("::", PORT), AdarHandler)
    server = threading.Thread(target=adar.serve_forever)
    server.start()
    while not stop:
        sleep(1)
    print(" done")
