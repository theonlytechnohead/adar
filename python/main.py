
import simplenc
import ipaddress
import netifaces
from zeroconf import ServiceBrowser, ServiceInfo, ServiceListener, Zeroconf
import socket


class AdarListener(ServiceListener):

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        print(f"Service updated: {name}")

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        print(f"Service removed: {name}")

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        print(f"Service added: {name}")

# https://stackoverflow.com/questions/39988525/find-local-non-loopback-ip-address-in-python
def get_local_non_loopback_ipv4_addresses():
    for interface in netifaces.interfaces():
        # Not all interfaces have an IPv4 address:
        if netifaces.AF_INET in netifaces.ifaddresses(interface):
            # Some interfaces have multiple IPv4 addresses:
            for address_info in netifaces.ifaddresses(interface)[netifaces.AF_INET]:
                address_object = ipaddress.IPv4Address(address_info["addr"])
                if not address_object.is_loopback:
                    yield address_info["addr"]


def zeroconf():
    zeroconf = Zeroconf()
    service_type = "_adar._tcp.local."
    properties = {
        "Description": "Network coding for automated distributed storage systems",
    }
    port = 6780
    fqdn = socket.getfqdn()
    hostname = socket.gethostname()
    ipv4 = list(get_local_non_loopback_ipv4_addresses())
    # https://stackoverflow.com/questions/52081008/get-most-recent-global-ipv6-address-of-interface
    ipv6 = socket.getaddrinfo(hostname, None, socket.AF_INET6)[1][4][0]
    print(f"{hostname}: {fqdn} ({ipv4}, {ipv6})")
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
    try:
        input("Press enter to exit...\n\n")
    finally:
        zeroconf.close()


if __name__ == "__main__":
    zeroconf()
