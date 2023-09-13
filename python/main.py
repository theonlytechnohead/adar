import math
import signal
import socket
import select
import socketserver
import threading
from Crypto.Cipher import ChaCha20
from time import sleep

import storage_sync
from simplenc import BinaryCoder
from advertise import *
from constants import *
from peer import *

stop = False

def identify_peer(address: str, timeout: int = 10):
    if address.startswith("::ffff:"):
        address = address.removeprefix("::ffff:")
    while 0 < timeout:
        for peer in peer_list:
            if address in peer.addresses:
                return peer
        sleep(1)
        timeout -= 1


class AdarHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        self.connection: socket.socket
        peer: Peer = None
        global stop
        while not stop:
            try:
                readable, writable, _ = select.select([self.connection,], [self.connection,], [], 1)
            except select.error as e:
                print(f"Socket error {e}, closing...")
                break
            if readable and writable:
                # try reading
                try:
                    self.raw_data = self.rfile.readline(2048)
                except:
                    # socket closed unexpectedly
                    break
                # check if there is any data
                if 0 == len(self.raw_data):
                    sleep(0.001)
                    continue
                # check if message end is received
                # TODO: maybe fetch more data / packets until end is recieved?
                # though there may need to be additional checks to ensure that data isn't garbage along the way
                if self.raw_data[-1].to_bytes() != b"\n":
                    # error, invalid message!
                    print(f"TCP message is invalid:", self.raw_data)
                    self.wfile.write(b"\n")
                    continue
                self.data = str(self.raw_data.strip(), "utf-8")
                if self.data.startswith("pair?"):
                    # TODO: check with user that pairing is okay
                    self.data = "sure".encode()
                elif self.data.startswith("connect?"):
                    print(f"\tconnection request from {self.client_address[0]}, identifying...")
                    self.data = "0".encode()
                    peer = identify_peer(self.client_address[0])
                    if peer == None:
                        print("\ttimed out trying to identify")
                        continue
                    # TODO: store this peer persistently for this connection
                    print(f"\tidentified peer: {peer.friendly_name}")
                    if peer.version == None:
                        break
                    self.data = f"{peer.version}".encode()
                elif self.data.startswith("key?"):
                    print(f"\tkey request from {peer.friendly_name}")
                    if peer.generator == None:
                        peer.generator = DiffieHellman(group=14, key_bits=1024)
                    public_key = peer.generator.get_public_key()
                    other_key = base64.b64decode(self.raw_data[4:-1])
                    peer.shared_key = peer.generator.generate_shared_key(other_key)
                    self.data = "key!".encode() + base64.b64encode(public_key) + "\n".encode()
                elif self.data.startswith("sync?"):
                    print(f"\tsync request from {peer.friendly_name}")
                    self.data = "0".encode()
                    timeout = 10
                    while peer.connection == None and peer.shared_key == None and peer.data_connection == None:
                        sleep(0.001)
                        timeout -= 0.001
                        if timeout <= 0:
                            break
                    if 0 < timeout:
                        self.data = "1".encode()
                elif self.data.startswith("ready"):
                    print(f"\tready request from {peer.friendly_name}")
                    self.data = "0".encode()
                    timeout = 10
                    while not peer.we_ready:
                        sleep(0.001)
                        timeout -= 0.001
                        if timeout <= 0:
                            break
                    if 0 < timeout:
                        self.data = "1".encode()
                elif self.data.startswith("bye"):
                    if peer == None:
                        break
                    print(f"{peer.friendly_name} said bye")
                    peer.connection.shutdown(socket.SHUT_RD)
                else:
                    if peer.we_ready and peer.ready: print("TCP", peer.friendly_name, self.data)
                    command = storage_sync.Command(int(self.data.split(":", 1)[0]))
                    arguments = self.data.strip().split(":", 1)[1]
                    match command:
                        case storage_sync.Command.LIST:
                            path = arguments
                            folders, files = storage_sync.list_local(path)
                            folders = f"{storage_sync.SEP}".join(folders)
                            files = f"{storage_sync.SEP}".join(files)
                            self.data = f"{folders}:{files}\n".encode()
                        case storage_sync.Command.STATS:
                            path = arguments
                            size, ctime, mtime, atime = storage_sync.stats_local(path)
                            self.data = f"{size}{storage_sync.SEP}{ctime}{storage_sync.SEP}{mtime}{storage_sync.SEP}{atime}\n".encode()
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
        # TODO: confirm dual-stack UDP server
        self.connection = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        self.connection.bind(address)
        self.stop = False

    def handle(self) -> None:
        while not self.stop:
            self.handle_connection()
    
    def handle_connection(self):
        # try reading
        try:
            message, address = self.connection.recvfrom(2048)
        except OSError:
            return
        # check if message end is received
        # TODO: maybe fetch more data / packets until end is recieved?
        # though there may need to be additional checks to ensure that data isn't garbage along the way
        if message[-1].to_bytes() != b"\n":
            # error, invalid message!
            print("UDP message is invalid:", message)
            return
        # identify peer
        peer = identify_peer(address[0])
        if peer == None:
            print("\ttimed out trying to identify")
            return
        # split command and arguments
        command, arguments = message.split(b":", 1)
        try:
            command = storage_sync.Command(int(command))
        except:
            print("UDP command is invalid", message)
            return
        if peer.we_ready and peer.ready: print("UDP", peer.friendly_name, command)
        arguments = arguments.decode().strip()
        # process command
        if command == storage_sync.Command.READ:
            """Received a read request, respond with network-coded data"""
            print("UDP", f"received a read request from {peer.friendly_name}")
            path, start, length = arguments.split(storage_sync.SEP)
            start = int(start)
            length = int(length)
            data = storage_sync.read_local(path, start, length)
        if command == storage_sync.Command.DATA or command == storage_sync.Command.WRITE:
            """Recieved network-coded data, decode and decrypt"""
            path, start, length, payload_length, _, _, _ = arguments.split(storage_sync.SEP)
            _, _, _, _, nonce, cata, data = message.split(storage_sync.SEP.encode())
            start = int(start)
            length = int(length)
            payload_length = int(payload_length)
            coefficient_bytes = math.ceil(payload_length / 8)
            # TODO: remove requirement to base64 decode
            nonce = base64.b64decode(nonce)
            cata = base64.b64decode(cata)
            data = base64.b64decode(data)
            coefficients = []
            # grab `coefficient_bytes` number of bytes at a time and use int.from_bytes w/ "big" endian
            for i in range(0, len(cata), coefficient_bytes):
                coefficient = bytearray(coefficient_bytes)
                for n in range(coefficient_bytes):
                    coefficient[n] = cata[i + n]
                coefficient = int.from_bytes(coefficient, "big")
                coefficients.append(coefficient)
            # decoding
            decoder = BinaryCoder(payload_length, 8, 1)
            for coefficient, byte in zip(coefficients, data):
                coefficient = [coefficient >> i & 1 for i in range(payload_length - 1, -1, -1)]
                bits = [byte >> i & 1 for i in range(8 - 1, -1, -1)]
                decoder.consume_packet(coefficient, bits)
            # reassembly
            data = bytearray()
            for packet in decoder.packet_vector:
                packet = int("".join(map(str, packet)), 2)
                data.extend((packet,))
            data = bytes(data)
            # decryption, ChaCha20
            ciphertext = base64.b64decode(data)
            cipher = ChaCha20.new(key=peer.shared_key[-32:], nonce=nonce)
            plaintext = cipher.decrypt(ciphertext)
        match command:
            case storage_sync.Command.READ:
                storage_sync.transmit_data(peer, storage_sync.Command.DATA, path, data, start=start, length=length)
            case storage_sync.Command.DATA:
                """Received data, presumably linked to a read request"""
                print("UDP", peer.friendly_name, f"data from a read: {path} ({start}->{start+length})", plaintext)
                storage_sync.reads[path] = plaintext
            case storage_sync.Command.WRITE:
                """Received a write command, process network-coded data"""
                print("UDP", peer.friendly_name, f"data to write: {path} ({start}->{start+length})", plaintext)
                storage_sync.write_local(path, start, length, plaintext)
    
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
        if peer.ready:
            storage_sync.transmit(peer, storage_sync.Command.DISCONNECT)
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
    adar_data = AdarDataHandler(("::", DATA_PORT))
    server = threading.Thread(target=adar.serve_forever)
    data_server = threading.Thread(target=adar_data.handle, daemon=True)
    server.start()
    data_server.start()
    service = advertise()
    while not stop:
        sleep(1)
    print("\tdone")
