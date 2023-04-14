
import simplenc
from zeroconf import ServiceBrowser, ServiceInfo, ServiceListener, Zeroconf
from socket import getfqdn, gethostname, gethostbyname, inet_aton


class AdarListener(ServiceListener):

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        print(f"Service updated: {name}")

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        print(f"Service removed: {name}")

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        print(f"Service added: {name}\n{info}")


def zeroconf():
    zeroconf = Zeroconf()
    type = "_adar._tcp.local."
    properties = {"Description": "Network coding for automated distributed storage systems"}
    port = 6780
    fqdn = getfqdn()
    hostname = gethostname()
    address =  gethostbyname(hostname)
    adar_info = ServiceInfo(
        type,
        name=f"{hostname}.{type}",
        port=port,
        properties=properties,
        server=fqdn,
        addresses=[inet_aton(address)])
    zeroconf.register_service(adar_info, 60)
    listener = AdarListener()
    browser = ServiceBrowser(zeroconf, type, listener)
    try:
        input("Press enter to exit...\n\n")
    finally:
        zeroconf.close()


if __name__ == "__main__":
    zeroconf()
