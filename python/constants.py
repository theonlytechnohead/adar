import machineid

ID = machineid.id().strip()  # unique ID for this instance
PORT = 6780  # port used for TCP transmission of control
DATA_PORT = 6781  # port used for UDP transmission of data
SERVICE = "_adar._tcp.local."  # suffix for DNS-SD service
SUPPORTED_VERSIONS = [1]  # versions supported by this implementation / instance

MOUNT_POINT = "mount"  # for presenting to the OS / user
ROOT_POINT = ".root"  # temporary
SYMBOL_DIRECTORY = ".symbols"  # holds symbols
METADATA_DIRECTORY = ".metadata"  # holds file metadata
ROOT_POINTS = (ROOT_POINT + "0", ROOT_POINT + "1")  # temporary