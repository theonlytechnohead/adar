import signal
import socket
import select
import socketserver
import threading
from time import sleep

import storage_sync
from simplenc import BinaryCoder
from advertise import *
from constants import *
from peer import *

stop = False


def identify_peer(address: str, timeout: int = 10):
    peer: Peer = None
    while peer == None and timeout != 0:
        for p in peer_list:
            if address in p.addresses:
                return p
        sleep(1)
        timeout -= 1


class AdarHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        self.connection: socket.socket
        global stop
        while not stop:
            try:
                readable, writable, _ = select.select([self.connection,], [self.connection,], [], 1)
            except select.error as e:
                print(f"Socket error {e}, closing...")
                break
            if readable and writable:
                try:
                    self.raw_data = self.rfile.readline(2048)
                except:
                    # socket closed unexpectedly
                    break
                if 0 == len(self.raw_data):
                    sleep(1)
                    continue
                try:
                    valid = self.raw_data.decode().endswith("\n")
                except UnicodeDecodeError as e:
                    # error, invalid message!
                    print(f"Caught a UnicodeDecodeError: {e.reason}")
                    self.wfile.write(bytes("\n", "utf-8"))
                    continue
                if not valid:
                    # error, invalid message!
                    print(f"TCP message is invalid:")
                    print(self.raw_data)
                    self.wfile.write(bytes("\n", "utf-8"))
                    continue
                self.data = str(self.raw_data.strip(), "utf-8")
                if self.data == "pair?":
                    self.data = b"sure"
                elif self.data.startswith("key?"):
                    print(f"\tpeer request from {self.client_address[0]}, identifying...")
                    peer = identify_peer(self.client_address[0])
                    if peer == None:
                        print("\ttimed out trying to identify")
                        continue
                    print(f"\tidentified peer: {peer.service_name.removesuffix(SERVICE)[:-1]}")
                    if peer.generator == None:
                        peer.generator = DiffieHellman(group=14, key_bits=1024)
                    public_key = peer.generator.get_public_key()
                    other_key = base64.b64decode(self.raw_data[4:-1])
                    peer.shared_key = peer.generator.generate_shared_key(other_key)
                    self.data = "key!".encode() + base64.b64encode(public_key) + "\n".encode()
                    # for testing
                    storage_sync.list("")
                else:
                    print("TCP", self.client_address[0], self.data)
                    command = storage_sync.Command(int(self.data.split(":", 1)[0]))
                    arguments = self.data.strip().split(":", 1)[1]
                    match command:
                        case storage_sync.Command.LIST:
                            path = arguments
                            # TODO: figure out how to return this value properly
                            listing = storage_sync.list_local(path)
                            print(listing)
                            self.data = "".encode()
                        case storage_sync.Command.CREATE:
                            path, directory = arguments.split(storage_sync.SEP)
                            storage_sync.create_local(path, bool(int(directory)))
                            self.data = "".encode()
                        case storage_sync.Command.RENAME:
                            path, new_path = arguments.split(storage_sync.SEP)
                            storage_sync.rename_local(path, new_path)
                            self.data = "".encode()
                        case storage_sync.Command.REMOVE:
                            path = arguments
                            storage_sync.remove_local(path)
                            self.data = "".encode()
                self.wfile.write(self.data)


class dual_stack(socketserver.ThreadingTCPServer):
    def server_bind(self) -> None:
        self.socket = socket.create_server(
            self.server_address, family=socket.AF_INET6, dualstack_ipv6=True)


class AdarDataHandler():
    def __init__(self, address: tuple) -> None:
        self.connection = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        self.connection.bind(address)
        self.stop = False

    def handle(self) -> None:
        while not self.stop:
            self.handle_connection()
    
    def handle_connection(self):
        try:
            message, address = self.connection.recvfrom(2048)
        except OSError:
            return
        try:
            valid = message.decode().endswith("\n")
        except UnicodeDecodeError as e:
            # error, invalid message!
            print(f"Caught a UnicodeDecodeError: {e.reason}")
            return
        if not valid:
            # error, invalid message!
            print(f"UDP message is invalid:")
            print(message)
            return
        print("UDP", address[0], message.decode())
        command = storage_sync.Command(int(message.decode().split(":", 1)[0]))
        arguments = message.decode().strip().split(":", 1)[1]
        match command:
            case storage_sync.Command.READ:
                """Received a read request, respond with network-coded data"""
                print("UDP", f"received a read request from {address[0]}")
                peer = identify_peer(address[0])
                if peer == None:
                    print("\ttimed out trying to identify")
                    return
                print("UDP", f"fulfilling read request for {peer.service_name.removesuffix(SERVICE)[:-1]}")
                path, start, length = arguments.split(storage_sync.SEP)
                start = int(start)
                length = int(length)
                data = storage_sync.read_local(path, start, length)
                storage_sync.transmit_data(peer, storage_sync.Command.DATA, path, data, start=start, length=length)
            case storage_sync.Command.DATA:
                """Received data, presumably linked to a read request"""
                path, start, length, _, _ = arguments.split(storage_sync.SEP)
                _, _, _, cata, data = message.split(storage_sync.SEP.encode())
                start = int(start)
                length = int(length)
                decoder = BinaryCoder(int(length), 8, 1)
                for coefficient, byte in zip(cata, data):
                    coefficient = [coefficient >> i & 1 for i in range(length - 1, -1, -1)]
                    bits = [byte >> i & 1 for i in range(8 - 1, -1, -1)]
                    decoder.consume_packet(coefficient, bits)
                data = bytearray()
                for packet in decoder.packet_vector:
                    packet = int("".join(map(str, packet)), 2)
                    data.extend((packet,))
                data = bytes(data)
                print("UDP", f"got data: {path} ({start}->{start+length})", data)
                storage_sync.reads[path] = data
            case storage_sync.Command.WRITE:
                """Received a write command, process network-coded data"""
                path, start, length, _, _ = arguments.split(storage_sync.SEP)
                _, _, _, cata, data = message.split(storage_sync.SEP.encode())
                start = int(start)
                length = int(length)
                decoder = BinaryCoder(int(length), 8, 1)
                print()
                for coefficient, byte in zip(cata, data):
                    coefficient = [coefficient >> i & 1 for i in range(length - 1, -1, -1)]
                    bits = [byte >> i & 1 for i in range(8 - 1, -1, -1)]
                    decoder.consume_packet(coefficient, bits)
                data = bytearray()
                for packet in decoder.packet_vector:
                    packet = int("".join(map(str, packet)), 2)
                    data.extend((packet,))
                data = bytes(data)
                storage_sync.write_local(path, start, length, data)
    
    def shutdown(self):
        self.stop = True
        self.connection.shutdown(socket.SHUT_RDWR)
        self.connection.close()


def handle(signum, frame):
    global stop
    print("\rStopping...", end="")
    service.close()
    adar.shutdown()
    adar_data.shutdown()
    for peer in peer_list:
        if peer.connection != None:
            peer.connection.shutdown(socket.SHUT_RDWR)
            peer.connection.close()
    if os.name == "posix":
        storage_fuse.destroy()
    if os.name == "nt":
        storage_projected.destroy()
    stop = True


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle)
    signal.signal(signal.SIGTERM, handle)
    if os.name == "posix":
        # TODO: bring FUSE to par with Projected File System
        import storage_fuse
        storage = threading.Thread(target=storage_fuse.create)
        storage.start()
    if os.name == "nt":
        import storage_projected
        storage = threading.Thread(target=storage_projected.create)
        storage.start()
    adar = dual_stack(("::", PORT), AdarHandler)
    adar_data = AdarDataHandler(("", DATA_PORT))
    server = threading.Thread(target=adar.serve_forever)
    data_server = threading.Thread(target=adar_data.handle, daemon=True)
    server.start()
    data_server.start()
    service = advertise()
    while not stop:
        sleep(1)
    print("\tdone")
