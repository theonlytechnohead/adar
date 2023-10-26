import ctypes
import os
import shutil
import sys

from simplenc import BinaryCoder

try:
    import ProjectedFS
except FileNotFoundError:
    print("Please enable the Windows Projected File System first!")
    print("You can do so in the 'Turn Windows features on or off' Control Panel applet")
    print("\tor")
    print("Open an elevated (Run as Administator) Powershell and run:")
    print("Enable-WindowsOptionalFeature -Online -FeatureName Client-ProjFS -NoRestart")
    exit()
import storage_sync
import storage_backing
from constants import *
from peer import *
from storage_metadata import *

DEBUG = False

FILE_ATTRIBUTE_HIDDEN = 0x02

# HRESULT
S_OK = 0x00000000
E_OUTOFMEMORY = 0x8007000E
E_INVALIDARG = 0x80070057

# HRESULT_FROM_WIN32()
ERROR_FILE_NOT_FOUND = 0x80070002
ERROR_INVALID_PARAMETER = 0x80070057

# http://support.microsoft.com/kb/167296
# How To Convert a UNIX time_t to a Win32 FILETIME or SYSTEMTIME
EPOCH_AS_FILETIME = 116444736000000000  # January 1, 1970 as MS file time
HUNDREDS_OF_NANOSECONDS = 10000000

def timestamp_to_filetime(ts):
    return EPOCH_AS_FILETIME + (int(ts) * HUNDREDS_OF_NANOSECONDS)


instanceHandle = None
sessions = dict()


@ProjectedFS.PRJ_START_DIRECTORY_ENUMERATION_CB
def start_directory_enumeration(callbackData, enumerationId):
    sessions[enumerationId.contents] = dict()
    return S_OK


@ProjectedFS.PRJ_END_DIRECTORY_ENUMERATION_CB
def end_directory_enumeration(callbackData, enumerationId):
    try:
        del sessions[enumerationId.contents]
        return S_OK
    except:
        pass


def get_fileinfo(path: str) -> ProjectedFS.PRJ_FILE_BASIC_INFO:
    fileInfo = ProjectedFS.PRJ_FILE_BASIC_INFO()
    if os.path.isfile(os.path.join(METADATA_DIRECTORY, path)):
        metadata = load_metadata(path)
        fileInfo.CreationTime = timestamp_to_filetime(from_ns(metadata.ctime_ns))
        fileInfo.LastWriteTime = timestamp_to_filetime(from_ns(metadata.mtime_ns))
        fileInfo.LastAccessTime = timestamp_to_filetime(from_ns(metadata.atime_ns))
        fileInfo.ChangeTime = timestamp_to_filetime(from_ns(metadata.mtime_ns))
        # fileInfo.FileAttributes = stats.st_file_attributes
    else:
        fileInfo.IsDirectory = True
    return fileInfo


def get_filesize(filename, info) -> ProjectedFS.PRJ_FILE_BASIC_INFO:
    if os.path.isfile(os.path.join(METADATA_DIRECTORY, filename)):
        metadata = load_metadata(filename)
        info.FileSize = metadata.length
    return info


@ProjectedFS.PRJ_GET_DIRECTORY_ENUMERATION_CB
def get_directory_enumeration(callbackData, enumerationId, searchExpression, dirEntryBufferHandle):
    try:
        if (("COMPLETED" not in sessions[enumerationId.contents]) or (callbackData.contents.Flags & ProjectedFS.PRJ_CB_DATA_FLAG_ENUM_RESTART_SCAN)):
            # TODO: searchExpression + wildcard support
            path = callbackData.contents.FilePathName
            full_path = os.path.join(METADATA_DIRECTORY, path)
            if DEBUG:
                print(
                    f"Getting directory enumeration: {callbackData.contents.FilePathName}")
            if os.path.exists(full_path):
                if os.path.isdir(full_path):
                    entries = [entry for entry in os.listdir(full_path)]
                else:
                    entries = [entry]
                for entry in entries:
                    if DEBUG:
                        print(f"Getting placeholder info: {entry}")
                    file_path = os.path.join(path, entry)
                    fileInfo = get_fileinfo(file_path)
                    # TODO: PrjFileNameCompare to determine correct sort order
                    ProjectedFS.PrjFillDirEntryBuffer(
                        entry, fileInfo, dirEntryBufferHandle)
                sessions[enumerationId.contents]["COMPLETED"] = True
            else:
                return ERROR_FILE_NOT_FOUND
        return S_OK
    except Exception as e:
        print(e)
        return ERROR_INVALID_PARAMETER


@ProjectedFS.PRJ_GET_PLACEHOLDER_INFO_CB
def get_placeholder_info(callbackData):
    if DEBUG:
        print(
            f"Fetching placeholder info: {callbackData.contents.FilePathName}")
    path = callbackData.contents.FilePathName
    full_path = os.path.join(METADATA_DIRECTORY, path)
    if os.path.exists(full_path):
        placeholderInfo = ProjectedFS.PRJ_PLACEHOLDER_INFO()
        info = get_fileinfo(path)
        info = get_filesize(callbackData.contents.FilePathName, info)
        placeholderInfo.FileBasicInfo = info
        # TODO: size vs size on disk?
        ProjectedFS.PrjWritePlaceholderInfo(
            callbackData.contents.NamespaceVirtualizationContext,
            path,
            placeholderInfo,
            ctypes.sizeof(placeholderInfo)
            )
        return S_OK
    else:
        return ERROR_FILE_NOT_FOUND


@ProjectedFS.PRJ_GET_FILE_DATA_CB
def get_file_data(callbackData, byteOffset, length):
    if DEBUG:
        print(
            f"Getting file data: {callbackData.contents.FilePathName} (+{byteOffset} for {length})")
    path = callbackData.contents.FilePathName
    full_path = os.path.join(METADATA_DIRECTORY, path)
    if os.path.exists(full_path):
        fileInfo = get_fileinfo(path)
        fileInfo = get_filesize(callbackData.contents.FilePathName, fileInfo)
        if length > fileInfo.FileSize:
            return E_INVALIDARG
        # read local symbols
        seed, symbols = storage_backing.read_file(callbackData.contents.FilePathName, 0, length * 2)
        output = bytearray(length)
        decoder = BinaryCoder(length, 8, seed)
        for symbol in symbols:
            coefficient, _ = decoder.generate_coefficients()
            symbol = [symbol >> i & 1 for i in range(8 - 1, -1, -1)]
            decoder.consume_packet(coefficient, symbol)
        for i in range(length):
            if decoder.is_symbol_decoded(i):
                symbol = decoder.get_decoded_symbol(i)
                output[i:i+1] = int("".join(map(str, symbol)), 2).to_bytes(1, "big")
        contents = bytes(output)
        # read network symbols
        # TODO: actually use this data
        network_contents = storage_sync.read(callbackData.contents.FilePathName, decoder, length)
        writeBuffer = ProjectedFS.PrjAllocateAlignedBuffer(callbackData.contents.NamespaceVirtualizationContext, length)
        if not writeBuffer:
            return E_OUTOFMEMORY
        ctypes.memmove(ctypes.c_void_p(writeBuffer), contents, length)
        ProjectedFS.PrjWriteFileData(
            callbackData.contents.NamespaceVirtualizationContext,
            callbackData.contents.DataStreamId,
            writeBuffer,
            byteOffset,
            length
            )
        ProjectedFS.PrjFreeAlignedBuffer(writeBuffer)
        return S_OK
    else:
        return ERROR_FILE_NOT_FOUND


@ProjectedFS.PRJ_NOTIFICATION_CB
def notified(callbackData, isDirectory, notification, destinationFileName, operationParameters):
    if DEBUG:
        print(f"Notified ({notification}) ", end="")
    match notification:
        case ProjectedFS.PRJ_NOTIFICATION_NEW_FILE_CREATED:
            if DEBUG:
                print(f"created: {callbackData.contents.FilePathName}")
            seed = storage_backing.create(callbackData.contents.FilePathName, bool(isDirectory))
            storage_sync.create(callbackData.contents.FilePathName, bool(isDirectory), seed)
        case ProjectedFS.PRJ_NOTIFICATION_FILE_RENAMED:
            if destinationFileName == "":
                if DEBUG:
                    print(f"moved elsewhere: {callbackData.contents.FilePathName}")
                storage_backing.remove(callbackData.contents.FilePathName)
                storage_sync.remove(callbackData.contents.FilePathName)
            elif callbackData.contents.FilePathName == "":
                if DEBUG:
                    print(f"moved here: {destinationFileName}")
                storage_backing.create(destinationFileName, isDirectory)
                storage_sync.create(destinationFileName, bool(isDirectory))
                # TODO: copy data?
            else:
                if DEBUG:
                    print(
                        f"renamed: {callbackData.contents.FilePathName} -> {destinationFileName}")
                storage_backing.rename(callbackData.contents.FilePathName, destinationFileName)
                storage_sync.rename(callbackData.contents.FilePathName, destinationFileName)
        case ProjectedFS.PRJ_NOTIFICATION_FILE_HANDLE_CLOSED_FILE_MODIFIED:
            if DEBUG:
                print(
                    f"close w/ modification: {callbackData.contents.FilePathName}")
            # https://stackoverflow.com/questions/55069340/windows-projected-file-system-read-only
            # writes always convert a placeholder into a "full" file (but we still get notifications, etc.)
            # so we need to be notified of this and rewrite the modified file into the backing store
            mount_path = os.path.join(MOUNT_POINT, callbackData.contents.FilePathName)
            size = os.stat(mount_path).st_size
            with open(mount_path, "rb") as file:
                data = file.read()
                seed = storage_backing.write(callbackData.contents.FilePathName, 0, size, data, real_path=mount_path)
                storage_sync.write(callbackData.contents.FilePathName, seed, data)
        case ProjectedFS.PRJ_NOTIFICATION_FILE_HANDLE_CLOSED_FILE_DELETED:
            if DEBUG:
                print(f"deleted: {callbackData.contents.FilePathName}")
            storage_backing.remove(callbackData.contents.FilePathName)
            storage_sync.remove(callbackData.contents.FilePathName)
    return S_OK


# Populate the required provider callback routines
# QueryFileNameCallback, NotificationCallback, and CancelCommandCallback are optional
callbackTable = ProjectedFS.PRJ_CALLBACKS()
callbackTable.StartDirectoryEnumerationCallback = start_directory_enumeration
callbackTable.EndDirectoryEnumerationCallback = end_directory_enumeration
callbackTable.GetDirectoryEnumerationCallback = get_directory_enumeration
callbackTable.GetPlaceholderInfoCallback = get_placeholder_info
callbackTable.GetFileDataCallback = get_file_data

callbackTable.NotificationCallback = notified


notificationMappings = (ProjectedFS.PRJ_NOTIFICATION_MAPPING(),)
notificationMappings[0].NotificationRoot = ""
notificationMappings[0].NotificationBitMask = ProjectedFS.PRJ_NOTIFY_NEW_FILE_CREATED | ProjectedFS.PRJ_NOTIFY_FILE_HANDLE_CLOSED_FILE_DELETED | ProjectedFS.PRJ_NOTIFY_FILE_HANDLE_CLOSED_FILE_MODIFIED | ProjectedFS.PRJ_NOTIFY_FILE_RENAMED

startOptions = ProjectedFS.PRJ_STARTVIRTUALIZING_OPTIONS()
startOptions.NotificationMappings = notificationMappings
startOptions.NotificationMappingsCount = len(notificationMappings)

# Hard coding our instance GUID for now
instanceId = ProjectedFS.GUID()
instanceId.Data1 = 0xD137C01A
instanceId.Data2 = 0xBAAD
instanceId.Data3 = 0xCAA7


def create():
    storage_backing.ensure(METADATA_DIRECTORY)
    storage_backing.ensure(SYMBOL_DIRECTORY)
    storage_backing.ensure(MOUNT_POINT)

    if ProjectedFS.PrjMarkDirectoryAsPlaceholder(os.path.abspath(MOUNT_POINT), None, None, instanceId) != S_OK:
        if DEBUG:
            print(
                f"Error marking {MOUNT_POINT} directory as placeholder, exiting...")
        sys.exit(1)

    if DEBUG:
        print("Starting virtualization instance")
    global instanceHandle
    instanceHandle = ProjectedFS.PRJ_NAMESPACE_VIRTUALIZATION_CONTEXT()
    if ProjectedFS.PrjStartVirtualizing(os.path.abspath(MOUNT_POINT), callbackTable, None, startOptions, instanceHandle) != S_OK:
        if DEBUG:
            print("Error starting virtualization, exiting...")
        sys.exit(1)


def destroy():
    ProjectedFS.PrjStopVirtualizing(instanceHandle)
    if DEBUG:
        print("Stopped virtualization instance")
    shutil.rmtree(MOUNT_POINT)
