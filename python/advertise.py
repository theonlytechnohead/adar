import ipaddress
import netifaces
import socket
from zeroconf import Zeroconf, ServiceListener, ServiceInfo, ServiceBrowser

from constants import *
from pairing import *
from peers import *

this_name = f"{socket.gethostname()}.{SERVICE}"


class AdarListener(ServiceListener):
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info.properties[b"uuid"].decode() != ID:
            friendlyname = name.removesuffix(f".{SERVICE}")
            peer = add_peer(info)
            print(f"Service discovered: {peer.service_name}")
            if paired:= check_pair(peer):
                print("\t(already paired)")
            else:
                paired = pair(friendlyname, peer)
            if paired:
                connect(peer)
                short_key = "-".join(f"{int(bit):03d}" for bit in peer.shared_key[:2])
                print(f"\tkey: {short_key}")

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        if name == this_name:
            return
        print(f"Service disappeared: {name}")
        index = None
        for i, p in enumerate(peer_list):
            if p.service_name == name:
                index = i
                break
        if index != None:
            if peer_list[index].connection != None:
                peer_list[index].connection.close()
            del peer_list[i]


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
    print(f"{hostname}@{fqdn} ({ID})")
    adar_info = ServiceInfo(
        SERVICE,
        name=this_name,
        port=PORT,
        properties=properties,
        server=fqdn,
        addresses=[*ipv4, *ipv6])
    zeroconf.register_service(adar_info)
    ServiceBrowser(zeroconf, SERVICE, AdarListener())
    return zeroconf
