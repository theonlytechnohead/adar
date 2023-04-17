import simplenc
import socketserver
import ipaddress
import netifaces
import threading
from zeroconf import ServiceBrowser, ServiceInfo, ServiceListener, Zeroconf
import socket
import uuid

ID = uuid.getnode()
PORT = 6780
SERVICE = "_adar._tcp.local."


class AdarListener(ServiceListener):
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        print(f"Service added: {name}")

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
    zeroconf.register_service(adar_info, 60)
    listener = AdarListener()
    browser = ServiceBrowser(zeroconf, SERVICE, listener)
    return zeroconf


class AdarHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        self.data = self.rfile.readline().strip()
        print(f"{self.client_address[0]}: {str(self.data, 'utf-8')}")
        self.wfile.write(self.data.upper())


class dual_stack(socketserver.TCPServer):
    def server_bind(self) -> None:
        self.socket = socket.create_server(
            self.server_address, family=socket.AF_INET6, dualstack_ipv6=True)


if __name__ == "__main__":
    service = zeroconf()
    adar = dual_stack(("::", PORT), AdarHandler)
    server = threading.Thread(target=adar.serve_forever, daemon=True)
    server.start()
    try:
        input("Press enter to exit...\n\n")
    finally:
        service.close()
        adar.shutdown()
