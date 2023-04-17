import socket
import sys

from main import SERVICE
from zeroconf import (IPVersion, ServiceBrowser, ServiceInfo, ServiceListener,
                      Zeroconf)

V4 = 0
V6 = 1


def hello(address, mode: int, port: int):
    HOST, PORT = address, port
    data = " ".join(sys.argv[1:])
    with socket.socket(socket.AF_INET6 if mode else socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((HOST, PORT))
        sock.sendall(bytes(data + "\n", "utf-8"))
        received = str(sock.recv(1024), "utf-8")
    print("Sent:     {}".format(data))
    print("Received: {}".format(received))


class AdarListener(ServiceListener):
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        v6 = info.parsed_addresses(IPVersion.V6Only)
        v4 = info.parsed_addresses(IPVersion.V4Only)
        mode = V6 if 0 < len(v6) else V4
        address = v6[0] if V6 else v4[0]
        hello(address, mode, info.port)

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass


zeroconf = Zeroconf()
listener = AdarListener()
browser = ServiceBrowser(zeroconf, SERVICE, listener)

try:
    input("Press enter to exit...\n\n")
finally:
    zeroconf.close()
