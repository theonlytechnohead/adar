import ctypes
import os
import shutil
import sys


import filetimes
import ProjectedFS
from peers import *

DEBUG = False

ROOT_POINT = ".root"
MOUNT_POINT = "mount"
FILE_ATTRIBUTE_HIDDEN = 0x02

# HRESULT
S_OK = 0x00000000
E_OUTOFMEMORY = 0x8007000E
E_INVALIDARG = 0x80070057

# HRESULT_FROM_WIN32()
ERROR_FILE_NOT_FOUND = 0x80070002
ERROR_INVALID_PARAMETER = 0x80070057

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


def get_fileinfo(path) -> ProjectedFS.PRJ_FILE_BASIC_INFO:
    fileInfo = ProjectedFS.PRJ_FILE_BASIC_INFO()
    stats = os.stat(path)
    fileInfo.CreationTime = filetimes.timestamp_to_filetime(stats.st_ctime)
    fileInfo.LastAccessTime = filetimes.timestamp_to_filetime(stats.st_atime)
    fileInfo.LastWriteTime = filetimes.timestamp_to_filetime(stats.st_mtime)
    fileInfo.ChangeTime = filetimes.timestamp_to_filetime(stats.st_mtime)
    fileInfo.FileAttributes = stats.st_file_attributes
    if os.path.isfile(path):
        fileInfo.FileSize = stats.st_size
    else:
        fileInfo.IsDirectory = True
    return fileInfo


@ProjectedFS.PRJ_GET_DIRECTORY_ENUMERATION_CB
def get_directory_enumeration(callbackData, enumerationId, searchExpression, dirEntryBufferHandle):
    try:
        if (("COMPLETED" not in sessions[enumerationId.contents]) or (callbackData.contents.Flags & ProjectedFS.PRJ_CB_DATA_FLAG_ENUM_RESTART_SCAN)):
            # TODO: searchExpression + wildcard support
            path = os.path.join(ROOT_POINT, callbackData.contents.FilePathName)
            if DEBUG:
                print(
                    f"Getting directory enumeration: {callbackData.contents.FilePathName}")
            if os.path.exists(path):
                if os.path.isdir(path):
                    entries = [entry for entry in os.listdir(path)]
                else:
                    entries = [entry]
                for entry in entries:
                    full_path = os.path.join(path, entry)
                    fileInfo = get_fileinfo(full_path)
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
    full_path = os.path.join(ROOT_POINT, path)
    if os.path.exists(full_path):
        placeholderInfo = ProjectedFS.PRJ_PLACEHOLDER_INFO()
        placeholderInfo.FileBasicInfo = get_fileinfo(full_path)
        # TODO: size vs size on disk?
        ProjectedFS.PrjWritePlaceholderInfo(
            callbackData.contents.NamespaceVirtualizationContext, path, placeholderInfo, ctypes.sizeof(placeholderInfo))
        return S_OK
    else:
        return ERROR_FILE_NOT_FOUND


@ProjectedFS.PRJ_GET_FILE_DATA_CB
def get_file_data(callbackData, byteOffset, length):
    if DEBUG:
        print(
            f"Getting file data: {callbackData.contents.FilePathName} (+{byteOffset} for {length})")
    path = callbackData.contents.FilePathName
    full_path = os.path.join(ROOT_POINT, path)
    if os.path.exists(full_path):
        fileInfo = get_fileinfo(full_path)
        if length > fileInfo.FileSize:
            return E_INVALIDARG
        with open(full_path, "rb") as file:
            file.seek(byteOffset)
            contents = file.read(length)
        writeBuffer = ProjectedFS.PrjAllocateAlignedBuffer(
            callbackData.contents.NamespaceVirtualizationContext, length)
        if not writeBuffer:
            return E_OUTOFMEMORY
        ctypes.memmove(ctypes.c_void_p(writeBuffer), contents, length)
        ProjectedFS.PrjWriteFileData(callbackData.contents.NamespaceVirtualizationContext,
                                     callbackData.contents.DataStreamId, writeBuffer, byteOffset, length)
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
            path = os.path.join(ROOT_POINT, callbackData.contents.FilePathName)
            if isDirectory:
                os.mkdir(path)
            else:
                open(path, "x").close()
        case ProjectedFS.PRJ_NOTIFICATION_FILE_RENAMED:
            if DEBUG:
                print(f"renamed: {callbackData.contents.FilePathName} -> {destinationFileName}")
            path = os.path.join(ROOT_POINT, callbackData.contents.FilePathName)
            new_path = os.path.join(ROOT_POINT, destinationFileName)
            os.rename(path, new_path)
        case ProjectedFS.PRJ_NOTIFICATION_FILE_HANDLE_CLOSED_FILE_MODIFIED:
            if DEBUG:
                print(f"close w/ modification: {callbackData.contents.FilePathname}")
            # https://stackoverflow.com/questions/55069340/windows-projected-file-system-read-only
            # writes always convert a placeholder into a "full" file (but we still get notifications, etc.)
            # so we need to be notified of this and rewrite the modified file into the backing store
            root_path = os.path.join(ROOT_POINT, callbackData.contents.FilePathName)
            mount_path = os.path.join(MOUNT_POINT, callbackData.contents.FilePathName)
            shutil.copy(mount_path, root_path)
        case ProjectedFS.PRJ_NOTIFICATION_FILE_HANDLE_CLOSED_FILE_DELETED:
            if DEBUG:
                print(f"deleted: {callbackData.contents.FilePathName}")
            path = os.path.join(ROOT_POINT, callbackData.contents.FilePathName)
            if isDirectory:
                shutil.rmtree(path)
            else:
                os.remove(path)
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
    if not os.path.exists(ROOT_POINT):
        if DEBUG:
            print(f"{ROOT_POINT} does not exist yet, creating...")
        os.mkdir(ROOT_POINT)

    if not os.path.isdir(ROOT_POINT):
        if DEBUG:
            print(f"{ROOT_POINT} is not a directory, exiting...")
        sys.exit(1)

    if not os.path.exists(MOUNT_POINT):
        if DEBUG:
            print(f"{MOUNT_POINT} does not exist yet, creating...")
        os.mkdir(MOUNT_POINT)

    if not os.path.isdir(MOUNT_POINT):
        if DEBUG:
            print(f"{MOUNT_POINT} is not a directory, exiting...")
        sys.exit(1)

    if ProjectedFS.PrjMarkDirectoryAsPlaceholder(MOUNT_POINT, None, None, instanceId) != S_OK:
        if DEBUG:
            print(
                f"Error marking {MOUNT_POINT} directory as placeholder, exiting...")
        sys.exit(1)

    if DEBUG:
        print("Starting virtualization instance")
    global instanceHandle
    instanceHandle = ProjectedFS.PRJ_NAMESPACE_VIRTUALIZATION_CONTEXT()
    if ProjectedFS.PrjStartVirtualizing(MOUNT_POINT, callbackTable, None, startOptions, instanceHandle) != S_OK:
        if DEBUG:
            print("Error starting virtualization, exiting...")
        sys.exit(1)


def destroy():
    ProjectedFS.PrjStopVirtualizing(instanceHandle)
    if DEBUG:
        print("Stopped virtualization instance")
    shutil.rmtree(MOUNT_POINT)
