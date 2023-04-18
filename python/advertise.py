import ipaddress
import netifaces
import socket
from zeroconf import Zeroconf, ServiceListener, ServiceInfo, ServiceBrowser

from main import SERVICE, ID, PORT
from pairing import *


class AdarListener(ServiceListener):
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if int(info.properties[b"uuid"]) != ID:
            friendlyname = name.removesuffix(f".{SERVICE}")
            print(f"Service discovered: {friendlyname}", end="")
            if check_pair(info):
                print(" (already paired)")
            else:
                print()
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
