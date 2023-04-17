
import simplenc
import socketserver
import ipaddress
import netifaces
import threading
from zeroconf import ServiceBrowser, ServiceInfo, ServiceListener, Zeroconf
import socket
import uuid


class AdarListener(ServiceListener):

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        print(f"Service updated: {name}")

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        print(f"Service removed: {name}")

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        print(f"Service added: {name}")


def get_local_non_loopback_ipv4_addresses():
    # https://stackoverflow.com/questions/39988525/find-local-non-loopback-ip-address-in-python
    for interface in netifaces.interfaces():
        # Not all interfaces have an IPv4 address:
        if netifaces.AF_INET in netifaces.ifaddresses(interface):
            # Some interfaces have multiple IPv4 addresses:
            for address_info in netifaces.ifaddresses(interface)[netifaces.AF_INET]:
                address_object = ipaddress.IPv4Address(address_info["addr"])
                if not address_object.is_loopback:
                    yield address_info["addr"]


def zeroconf() -> Zeroconf:
    zeroconf = Zeroconf()
    service_type = "_adar._tcp.local."
    id = uuid.getnode()
    properties = {
        "Description": "Network coding for automated distributed storage systems",
        "uuid": id
    }
    port = 6780
    fqdn = socket.getfqdn()
    hostname = socket.gethostname()
    ipv4 = list(get_local_non_loopback_ipv4_addresses())
    # https://stackoverflow.com/questions/52081008/get-most-recent-global-ipv6-address-of-interface
    ipv6 = socket.getaddrinfo(hostname, None, socket.AF_INET6)[1][4][0]
    print(f"{hostname} ({id}): {fqdn} ({ipv4}, {ipv6})")
    adar_info = ServiceInfo(
        service_type,
        name=f"{hostname}.{service_type}",
        port=port,
        properties=properties,
        server=fqdn,
        addresses=[*ipv4, ipv6])
    zeroconf.register_service(adar_info, 60)
    listener = AdarListener()
    browser = ServiceBrowser(zeroconf, service_type, listener)
    return zeroconf


class AdarHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        self.data = self.rfile.readline().strip()
        print(f"{self.client_address[0]} wrote: {str(self.data, 'utf-8')}")
        self.wfile.write(self.data.upper())


class dual_stack(socketserver.TCPServer):
    def server_bind(self) -> None:
        self.socket = socket.create_server(
            self.server_address, family=socket.AF_INET6, dualstack_ipv6=True)


def server() -> socketserver.TCPServer:
    address = ("::", 6780)
    server = dual_stack(address, AdarHandler)
    return server


if __name__ == "__main__":
    service = zeroconf()
    adar = server()
    thread = threading.Thread(target=adar.serve_forever, daemon=True)
    thread.start()
    try:
        input("Press enter to exit...\n\n")
    finally:
        service.close()
        adar.shutdown()
