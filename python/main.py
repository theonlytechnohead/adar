import ipaddress
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

exit = False


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


def zeroconf() -> Zeroconf:
    zeroconf = Zeroconf()
    properties = {
        "Description": "Network coding for automated distributed storage systems",
        "uuid": ID
    }
    fqdn = socket.getfqdn()
    hostname = socket.gethostname()
    ipv4 = list(get_local_non_loopback_ipv4_addresses())
    # https://stackoverflow.com/questions/52081008/get-most-recent-global-ipv6-address-of-interface
    ipv6 = socket.getaddrinfo(hostname, None, socket.AF_INET6)[1][4][0]
    print(f"{hostname} ({ID}): {fqdn} ({ipv4}, {ipv6})")
    adar_info = ServiceInfo(
        SERVICE,
        name=f"{hostname}.{SERVICE}",
        port=PORT,
        properties=properties,
        server=fqdn,
        addresses=[*ipv4, ipv6])
    zeroconf.register_service(adar_info)
    ServiceBrowser(zeroconf, SERVICE, AdarListener())
    return zeroconf


class AdarHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        self.data = self.rfile.readline().strip()
        print(f"{self.client_address[0]}: {str(self.data, 'utf-8')}")
        if self.data == "pair?":
            self.data = "sure"
        self.wfile.write(self.data.upper())


class dual_stack(socketserver.TCPServer):
    def server_bind(self) -> None:
        self.socket = socket.create_server(
            self.server_address, family=socket.AF_INET6, dualstack_ipv6=True)


def parse_service(info: ServiceInfo) -> tuple[str, socket.AddressFamily]:
    v6 = info.parsed_addresses(IPVersion.V6Only)
    if 0 < len(v6):
        return v6[0], socket.AF_INET6
    return info.parsed_addresses(IPVersion.V4Only)[0], socket.AF_INET


def request_pair(info: ServiceInfo) -> bool:
    accepted = False
    address, mode = parse_service(info)
    with socket.socket(mode, socket.SOCK_STREAM) as sock:
        sock.connect((address, PORT))
        sock.sendall(bytes("pair?" + "\n", "utf-8"))
        received = str(sock.recv(1024), "utf-8")
        accepted = True if received == "sure" else False
    return accepted


def pair(name: str, info: ServiceInfo):
    confirm = input(f"Do you want to pair with {name}? [Y/n] ")
    if confirm.lower() == "y" or confirm == "":
        if request_pair(info):
            print("Pairing accepted")
        else:
            print("Pairing failed")


def handle(signum, frame):
    global exit
    print("Exiting...")
    service.close()
    adar.shutdown()
    exit = True


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle)
    signal.signal(signal.SIGTERM, handle)
    service = zeroconf()
    adar = dual_stack(("::", PORT), AdarHandler)
    server = threading.Thread(target=adar.serve_forever)
    server.start()
    while not exit:
        sleep(1)
