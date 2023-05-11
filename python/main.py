import signal
import socket
import socketserver
import threading
from time import sleep

from advertise import *
from constants import *
from peers import *

stop = False

class AdarHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        self.data = str(self.rfile.readline().strip(), "utf-8")
        if self.data == "pair?":
            self.data = b"sure"
        elif self.data.startswith("key?"):
            generator = generators[self.client_address]
            raw_data = self.data[4:].encode()
            shared_key = generator.generate_shared_key(raw_data)
            self.data = bytes("key!", "utf-8") + generator.get_public_key() + bytes("\n", "utf-8")
            keys[self.client_address] = shared_key
        else:
            print(f"{self.client_address[0]}: {self.data}")
            self.data = bytes(self.data.upper(), "utf-8")
        self.wfile.write(self.data)


class dual_stack(socketserver.TCPServer):
    def server_bind(self) -> None:
        self.socket = socket.create_server(
            self.server_address, family=socket.AF_INET6, dualstack_ipv6=True)


def handle(signum, frame):
    global stop
    print("\rStopping...", end="")
    service.close()
    adar.shutdown()
    if os.name == "posix":
        storage_fuse.destroy()
    if os.name == "nt":
        storage_projected.destroy()
    stop = True


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle)
    signal.signal(signal.SIGTERM, handle)
    service = zeroconf()
    adar = dual_stack(("::", PORT), AdarHandler)
    server = threading.Thread(target=adar.serve_forever)
    server.start()
    if os.name == "posix":
        # TODO: hookup callbacks w/ `peers`
        import storage_fuse
        storage = threading.Thread(target=storage_fuse.create)
        storage.start()
    if os.name == "nt":
        # TODO: use the Windows Projected File System via PyProjFS
        import storage_projected
        storage = threading.Thread(target=storage_projected.create)
        storage.start()
    while not stop:
        sleep(1)
    print("\tdone")
