import math
import signal
import socket
import select
import socketserver
import threading
from Crypto.Cipher import ChaCha20_Poly1305
from time import sleep

import storage_sync
from simplenc import BinaryCoder
from advertise import *
from constants import *
from peer import *

stop = False


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
                    self.raw_data = self.rfile.readline(1500)
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
                if self.raw_data[-1].to_bytes(1, "big") != b"\n":
                    # error, invalid message!
                    print(f"TCP message is invalid:", self.raw_data)
                    self.wfile.write(b"\n")
                    continue
                self.data = str(self.raw_data.strip(), "utf-8")
                if peer and peer.we_ready and peer.ready: print("TCP", peer.friendly_name, self.data)
                command = storage_sync.Command(int(self.data.split(":", 1)[0]))
                # TODO: test for command first, then determine whether arguments need to be split off?
                arguments = self.data.strip().split(":", 1)[1]
                # TODO: check peer is connected and all is ready before processing any commands
                match command:
                    case storage_sync.Command.PAIR:
                        self.data = int.to_bytes(0, 1, "big")
                        # TODO: check compatibility
                        # TODO: check with user that pairing is okay
                        self.data = int.to_bytes(1, 1, "big")
                    case storage_sync.Command.CONNECT:
                        print(f"\tconnection request from {self.client_address[0]}, identifying...")
                        self.data = int.to_bytes(0, 1, "big")
                        peer = storage_sync.identify_peer(self.client_address[0])
                        if peer == None:
                            print("\ttimed out trying to identify")
                            break
                        print(f"\tidentified peer: {peer.friendly_name}")
                        timeout = 30
                        while peer.version == None and not check_pair(peer):
                            sleep(0.001)
                            timeout -= 0.001
                            if timeout < 0:
                                break
                        if 0 < timeout:
                            self.data = int.to_bytes(peer.version, 1, "big")
                    case storage_sync.Command.KEY:
                        print(f"\tkey request from {peer.friendly_name}")
                        if peer.generator == None:
                            peer.generator = DiffieHellman(group=16, key_bits=1024)
                        public_key = peer.generator.get_public_key()
                        other_key = base64.b64decode(self.raw_data[2:-1])
                        peer.shared_key = peer.generator.generate_shared_key(other_key)
                        self.data = public_key
                    case storage_sync.Command.SYNC:
                        print(f"\tsync request from {peer.friendly_name}")
                        self.data = int.to_bytes(0, 1, "big")
                        timeout = 10
                        while peer.connection == None and peer.shared_key == None and peer.data_connection == None:
                            sleep(0.001)
                            timeout -= 0.001
                            if timeout <= 0:
                                break
                        if 0 < timeout:
                            self.data = int.to_bytes(1, 1, "big")
                    case storage_sync.Command.READY:
                        print(f"\tready request from {peer.friendly_name}")
                        self.data = int.to_bytes(0, 1, "big")
                        timeout = 10
                        while not peer.we_ready:
                            sleep(0.001)
                            timeout -= 0.001
                            if timeout <= 0:
                                break
                        if 0 < timeout:
                            self.data = int.to_bytes(1, 1, "big")
                    case storage_sync.Command.DISCONNECT:
                        if peer == None:
                            break
                        print(f"{peer.friendly_name} said bye")
                        self.finish()
                        return
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
    def __init__(self, v4_address: tuple, v6_address: tuple) -> None:
        if os.name == "nt":
            self.v4_connection = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.v4_connection.bind(v4_address)
        self.v6_connection = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        self.v6_connection.bind(v6_address)
        self.stop = False

    def handle(self) -> None:
        if os.name == "nt":
            threading.Thread(target=self.handle_threaded, args=(self.v4_connection,)).start()
        threading.Thread(target=self.handle_threaded, args=(self.v6_connection,)).start()
        
    
    def handle_threaded(self, connection: socket.socket):
        while not self.stop:
            self.handle_connection(connection)
    
    def handle_connection(self, connection: socket.socket):
        # try reading
        try:
            message, address = connection.recvfrom(1500)
        except OSError:
            return
        # check if message end is received
        # TODO: must fetch more data / packets until fully decoded!
        # though there may need to be additional checks to ensure that data isn't garbage along the way
        if message[-1].to_bytes(1, "big") != b"\n":
            # error, invalid message!
            print("UDP message is invalid:", message)
            return
        # identify peer
        peer = storage_sync.identify_peer(address[0])
        if peer == None:
            print("\ttimed out trying to identify")
            return
        timeout = 10
        while not peer.data_connection:
            sleep(0.001)
            timeout -= 0.001
            if timeout < 0:
                return
        # split command and arguments
        header, arguments = message.split(storage_sync.SEP.encode(), 1)
        try:
            command = storage_sync.Command(header[0])
        except:
            print("UDP command is invalid", message)
            return
        if peer.we_ready and peer.ready: print("UDP", peer.friendly_name, command)
        arguments = arguments.rstrip()
        # process command
        if command == storage_sync.Command.READ:
            """Received a read request, respond with network-coded data"""
            print("UDP", f"received a read request from {peer.friendly_name}")
            path = header[1:].decode()
            skip, equations = arguments.decode().split(storage_sync.SEP)
            skip = int(skip)
            equations = int(equations)
            seed, symbols = storage_sync.read_local(path, skip, equations)
            data = bytes(symbols)
        if command == storage_sync.Command.DATA or command == storage_sync.Command.WRITE:
            """Recieved network-coded data, decode and decrypt"""
            path = header[1:].decode()
            i = 0
            seed = int.from_bytes(arguments[i:i+8], "big")
            i += 8
            payload_length = int.from_bytes(arguments[i:i+8], "big")
            i += 8
            coefficient_bytes = max(math.ceil(payload_length / 8), 1)
            nonce = arguments[i:i+24]
            i += 24
            cata_length = int.from_bytes(arguments[i:i+2], "big")
            i += 2
            cata = arguments[i:i+cata_length]
            i += cata_length
            data_length = int.from_bytes(arguments[i:i+2], "big")
            i += 2
            data = arguments[i:i+data_length]
            i += data_length
            tag = arguments[i:i+16]
            i += 16
            coefficients = []
            # grab `coefficient_bytes` number of bytes at a time and use int.from_bytes w/ "big" endian
            for i in range(0, len(cata), coefficient_bytes):
                coefficient = bytearray(coefficient_bytes)
                for n in range(coefficient_bytes):
                    coefficient[n] = cata[i + n]
                coefficient = int.from_bytes(coefficient, "big")
                coefficients.append(coefficient)
            # decoding
            storage_sync.reads[path].decoder = BinaryCoder(payload_length, 8, seed)
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
            # decryption, XChaCha20-Poly1305
            cipher = ChaCha20_Poly1305.new(key=peer.shared_key[-32:], nonce=nonce)
            cipher.update(path.encode())
            plaintext = cipher.decrypt_and_verify(data, tag)
            # process the coded symbols still, not actual file data yet
            generated_coefficients, _ = storage_sync.reads[path].decoder.generate_coefficients()
            for coefficient, byte in zip(generated_coefficients, plaintext):
                coefficient = [coefficient >> i & 1 for i in range(payload_length - 1, -1, -1)]
                bits = [byte >> i & 1 for i in range(8 - 1, -1, -1)]
                storage_sync.reads[path].decoder.consume_packet(coefficient, bits)
            output = bytearray(payload_length)
            for i in range(payload_length):
                if storage_sync.reads[path].decoder.is_symbol_decoded(i):
                    symbol = storage_sync.reads[path].decoder.get_decoded_symbol(i)
                    output[i:i+1] = int("".join(map(str, symbol)), 2).to_bytes(1, "big")
            plaintext = bytes(output)
        match command:
            case storage_sync.Command.READ:
                storage_sync.transmit_data(peer, storage_sync.Command.DATA, path, data, seed=seed, skip=skip)
            case storage_sync.Command.DATA:
                """Received data, presumably linked to a read request"""
                print("UDP", peer.friendly_name, f"data from a read: {path}", plaintext)
                storage_sync.reads[path].data = plaintext
            case storage_sync.Command.WRITE:
                """Received a write command, process network-coded data"""
                print("UDP", peer.friendly_name, f"data to write: {path}", plaintext)
                storage_sync.write_local(path, 0, len(plaintext), plaintext)
    
    def shutdown(self):
        self.stop = True
        if os.name == "nt":
            self.v4_connection.close()
        self.v6_connection.close()


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
    adar_data = AdarDataHandler(("0.0.0.0", DATA_PORT), ("::", DATA_PORT))
    server = threading.Thread(target=adar.serve_forever)
    data_server = threading.Thread(target=adar_data.handle, daemon=True)
    server.start()
    data_server.start()
    service = advertise()
    while not stop:
        sleep(0.1)
    print("\tdone")
