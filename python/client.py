import socket
import sys
from zeroconf import ServiceBrowser, ServiceInfo, ServiceListener, Zeroconf, IPVersion


def hello(v6, v4, port):
    HOST, PORT = v6[0] if 0 < len(v6) else v4[0], port
    data = " ".join(sys.argv[1:])
    with socket.socket(socket.AF_INET6 if 0 < len(v6) else socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((HOST, PORT))
        sock.sendall(bytes(data + "\n", "utf-8"))
        received = str(sock.recv(1024), "utf-8")
    print("Sent:     {}".format(data))
    print("Received: {}".format(received))


class AdarListener(ServiceListener):

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        print(f"Service updated: {name}")

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        print(f"Service removed: {name}")

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        hello(info.parsed_addresses(IPVersion.V6Only), info.parsed_addresses(IPVersion.V4Only), info.port)


zeroconf = Zeroconf()
listener = AdarListener()
browser = ServiceBrowser(zeroconf, "_adar._tcp.local.", listener)

try:
	input("Press enter to exit...\n\n")
finally:
	zeroconf.close()