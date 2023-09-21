import ipaddress
import netifaces
import socket
from zeroconf import Zeroconf, ServiceListener, ServiceInfo, ServiceBrowser

import storage_sync

from constants import *
from pairing import *
from peer import *

this_name = f"{socket.gethostname()}.{SERVICE}"

class AdarListener(ServiceListener):
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info.properties[b"uuid"].decode() == ID:
            # this is us, ignore
            return
        # TODO: check if peer is already connected
        peer = add_peer(info)
        print(f"Discovered {peer.friendly_name}")
        compatible_versions = [version for version in peer.versions if version in SUPPORTED_VERSIONS]
        if 0 == len(compatible_versions):
            # no compatible versions found, ignore
            return
        peer.version = max(compatible_versions)
        paired = check_pair(peer)
        if not paired:
            paired = pair(peer)
        if not paired:
            # they didn't want to pair, ignore
            # TODO: remove peer from list
            return
        connected = connect(peer)
        if not connected:
            # they didn't want to, or couldn't connect, ignore
            # TODO: remove peer from list
            return
        short_key = "-".join(f"{int(bit):03d}" for bit in peer.shared_key[:2])
        print(f"\tkey: {short_key}")
        sync = storage_sync.transmit(peer, storage_sync.Command.SYNC).join()
        if not sync:
            # sync failed, ignore
            # TODO: retry? or remove peer from list
            return
        peer.we_ready = storage_sync.sync().join()
        print("we are ready, telling peer")
        peer.ready = storage_sync.transmit(peer, storage_sync.Command.READY).join()
        # TODO: if peer is not ready, remove peer from list

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        # TODO: check if the service is one of our peers, and if the hash has changed, disconnect and try again?
        pass

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        if name == this_name:
            return
        print(f"{name.removesuffix(SERVICE)[:-1]} disappeared")
        index = None
        for i, p in enumerate(peer_list):
            if p.service_name == name:
                index = i
                break
        if index != None:
            if peer_list[index].connection != None:
                peer_list[index].connection.shutdown(socket.SHUT_RDWR)
                peer_list[index].connection.close()
            del peer_list[index]


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


def advertise() -> Zeroconf:
    zeroconf = Zeroconf()
    properties = {
        "Description": "Network coding for automated distributed storage systems",
        "uuid": ID,
        "versions": storage_sync.SEP.join([str(version) for version in SUPPORTED_VERSIONS])
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
