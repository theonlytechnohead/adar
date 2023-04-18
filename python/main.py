import signal
import socket
import socketserver
import threading
import uuid
from time import sleep

from advertise import *

ID = uuid.getnode()
PORT = 6780
SERVICE = "_adar._tcp.local."

stop = False


class AdarHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        self.data = str(self.rfile.readline().strip(), "utf-8")
        if self.data == "pair?":
            self.data = b"sure"
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
    print("Stopping...", end="")
    service.close()
    adar.shutdown()
    stop = True


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle)
    signal.signal(signal.SIGTERM, handle)
    service = zeroconf()
    adar = dual_stack(("::", PORT), AdarHandler)
    server = threading.Thread(target=adar.serve_forever)
    server.start()
    while not stop:
        sleep(1)
    print(" done")
