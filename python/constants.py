import machineid

ID = machineid.id().strip()
PORT = 6780
DATA_PORT = 6781
SERVICE = "_adar._tcp.local."
SUPPORTED_VERSIONS = [1]

MOUNT_POINT = "mount"
ROOT_POINT = ".root"
ROOT_POINTS = (ROOT_POINT + "0", ROOT_POINT + "1")