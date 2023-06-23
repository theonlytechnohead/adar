import signal
import socket
import socketserver
import threading
from time import sleep

import storage_sync
from advertise import *
from constants import *
from peers import *

stop = False


class AdarHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        self.raw_data = self.rfile.readline(2048)
        try:
            valid = self.raw_data.decode().endswith("\n")
        except UnicodeDecodeError as e:
            # error, invalid message!
            print(f"Caught a UnicodeDecodeError: {e.reason}")
            self.wfile.write(bytes("\n", "utf-8"))
            return
        if not valid:
            # error, invalid message!
            print(f"Message is invalid!")
            self.wfile.write(bytes("\n", "utf-8"))
            return
        self.data = str(self.raw_data.strip(), "utf-8")
        if self.data == "pair?":
            self.data = b"sure"
        elif self.data.startswith("key?"):
            peer: Peer = None
            while peer == None:
                for p in peer_list:
                    if self.client_address[0] in p.addresses:
                        peer = p
                        break
                sleep(1)
            if peer.generator == None:
                peer.generator = DiffieHellman(group=14, key_bits=1024)
            public_key = peer.generator.get_public_key()
            other_key = base64.b64decode(self.raw_data[4:-1])
            peer.shared_key = peer.generator.generate_shared_key(other_key)
            self.data = "key!".encode() + base64.b64encode(public_key) + "\n".encode()
        else:
            print(f"{self.client_address[0]}: {self.data}")
            if self.data.startswith(str(storage_sync.Command.CREATE)):
                arguments = self.data.strip().split(":")[1]
                path, directory = arguments.split(storage_sync.SEP)
                storage_sync.create_local(path, directory == "1")
            if self.data.startswith(str(storage_sync.Command.READ)):
                arguments = self.data.strip().split(":")[1]
                path, start, length = arguments.split(storage_sync.SEP)
                storage_sync.read_local(path, int(start), int(length))
            if self.data.startswith(str(storage_sync.Command.RENAME)):
                arguments = self.data.strip().split(":")[1]
                path, new_path = arguments.split(storage_sync.SEP)
                storage_sync.rename_local(path, new_path)
            if self.data.startswith(str(storage_sync.Command.WRITE)):
                arguments = self.data.strip().split(":")[1]
                path, start, length, _ = arguments.split(storage_sync.SEP)
                _, _, _, data = self.raw_data.split(storage_sync.SEP.encode())
                storage_sync.write_local(path, int(start), int(length), data)
            if self.data.startswith(str(storage_sync.Command.REMOVE)):
                arguments = self.data.strip().split(":")[1]
                path = arguments
                storage_sync.remove_local(path)
            self.data = bytes(self.data.upper(), "utf-8")
        self.wfile.write(self.data)


class dual_stack(socketserver.ThreadingTCPServer):
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
    adar = dual_stack(("::", PORT), AdarHandler)
    server = threading.Thread(target=adar.serve_forever)
    server.start()
    service = zeroconf()
    while not stop:
        sleep(1)
    print("\tdone")
