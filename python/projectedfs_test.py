import os
import shutil
import sys
import ctypes
import ProjectedFS

ROOT_POINT = "./.root"
MOUNT_POINT = "./mount"
DEBUG = True

# HRESULT
S_OK = 0x00000000
E_OUTOFMEMORY = 0x8007000E
E_INVALIDARG = 0x80070057

# HRESULT_FROM_WIN32()
ERROR_FILE_NOT_FOUND = 0x80070002
ERROR_INVALID_PARAMETER = 0x80070057

# file metadata
fileBasicInfo = ProjectedFS.PRJ_FILE_BASIC_INFO()
fileBasicInfo.IsDirectory = False
fileBasicInfo.FileSize = 0x1000

sessions = dict()
virt_file = "testing.txt"


@ProjectedFS.PRJ_START_DIRECTORY_ENUMERATION_CB
def start_directory_enumeration(callbackData, enumerationId):
    # if DEBUG:
    # print(f"Starting directory enumeration: {enumerationId.contents}")
    sessions[enumerationId.contents] = dict()
    return S_OK


@ProjectedFS.PRJ_END_DIRECTORY_ENUMERATION_CB
def end_directory_enumeration(callbackData, enumerationId):
    # if DEBUG:
    # print(f"Stopping directory enumeration: {enumerationId.contents}")
    try:
        del sessions[enumerationId.contents]
        return S_OK
    except:
        pass

# just fill out a dummy entry for virt_file


@ProjectedFS.PRJ_GET_DIRECTORY_ENUMERATION_CB
def get_directory_enumeration(callbackData, enumerationId, searchExpression, dirEntryBufferHandle):
    if DEBUG:
        print(f"Getting directory enumeration: /{searchExpression}")
    try:
        if (("COMPLETED" not in sessions[enumerationId.contents]) or (callbackData.Flags & ProjectedFS.PRJ_CB_DATA_FLAG_ENUM_RESTART_SCAN)):
            if ProjectedFS.PrjFileNameMatch(virt_file, searchExpression):
                ProjectedFS.PrjFillDirEntryBuffer(
                    virt_file, fileBasicInfo, dirEntryBufferHandle)
                sessions[enumerationId.contents]["COMPLETED"] = True
            else:
                return ERROR_FILE_NOT_FOUND
        return S_OK
    except:
        return ERROR_INVALID_PARAMETER


@ProjectedFS.PRJ_GET_PLACEHOLDER_INFO_CB
def get_placeholder_info(callbackData):
    if DEBUG:
        print(
            f"Fetching placeholder info: {callbackData.contents.FilePathName}")
    if ProjectedFS.PrjFileNameMatch(virt_file, callbackData.contents.FilePathName):
        PlaceholderInfo = ProjectedFS.PRJ_PLACEHOLDER_INFO()
        PlaceholderInfo.FileBasicInfo = fileBasicInfo
        ProjectedFS.PrjWritePlaceholderInfo(
            callbackData.contents.NamespaceVirtualizationContext, virt_file, PlaceholderInfo, ctypes.sizeof(PlaceholderInfo))
        return S_OK
    else:
        return ERROR_FILE_NOT_FOUND


@ProjectedFS.PRJ_GET_FILE_DATA_CB
def get_file_data(callbackData, byteOffset, length):
    if DEBUG:
        print(f"Getting file data: {callbackData.contents.FilePathName}")
    if length > fileBasicInfo.FileSize:
        return E_INVALIDARG

    writeBuffer = ProjectedFS.PrjAllocateAlignedBuffer(
        callbackData.contents.NamespaceVirtualizationContext, length)
    if not writeBuffer:
        return E_OUTOFMEMORY

    ctypes.memmove(ctypes.c_void_p(writeBuffer), "A" * length, length)
    ProjectedFS.PrjWriteFileData(callbackData.contents.NamespaceVirtualizationContext,
                                 callbackData.contents.DataStreamId, writeBuffer, byteOffset, length)
    ProjectedFS.PrjFreeAlignedBuffer(writeBuffer)
    return S_OK


notification_table = {
    0x00000002: "PRJ_NOTIFICATION_FILE_OPENED",
    0x00000004: "PRJ_NOTIFICATION_NEW_FILE_CREATED",
    0x00000008: "PRJ_NOTIFICATION_FILE_OVERWRITTEN",
    0x00000010: "PRJ_NOTIFICATION_PRE_DELETE",
    0x00000020: "PRJ_NOTIFICATION_PRE_RENAME",
    0x00000040: "PRJ_NOTIFICATION_PRE_SET_HARDLINK",
    0x00000080: "PRJ_NOTIFICATION_FILE_RENAMED",
    0x00000100: "PRJ_NOTIFICATION_HARDLINK_CREATED",
    0x00000200: "PRJ_NOTIFICATION_FILE_HANDLE_CLOSED_NO_MODIFICATION",
    0x00000400: "PRJ_NOTIFICATION_FILE_HANDLE_CLOSED_FILE_MODIFIED",
    0x00000800: "PRJ_NOTIFICATION_FILE_HANDLE_CLOSED_FILE_DELETED",
    0x00001000: "PRJ_NOTIFICATION_FILE_PRE_CONVERT_TO_FULL",
}


@ProjectedFS.PRJ_NOTIFICATION_CB
def notified(callbackData, isDirectory, notification, destinationFileName, operationParameters):
    if notification == ProjectedFS.PRJ_NOTIFICATION_FILE_OPENED:
        return S_OK
    message = notification_table[notification]
    if DEBUG:
        print(f"Notified: {message}")
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


notificationMappings = [ProjectedFS.PRJ_NOTIFICATION_MAPPING(),]
notificationMappings[0].NotificationRoot = ""
notificationMappings[0].NotificationBitMask = ProjectedFS.PRJ_NOTIFY_NEW_FILE_CREATED

startOptions = ProjectedFS.PRJ_STARTVIRTUALIZING_OPTIONS()
startOptions.NotificationMappings = notificationMappings
startOptions.NotificationMappingsCount = len(notificationMappings)

# Hard coding our instance GUID for now
instanceId = ProjectedFS.GUID()
instanceId.Data1 = 0xD137C01A
instanceId.Data2 = 0xBAAD
instanceId.Data3 = 0xCAA7

if not os.path.exists(MOUNT_POINT):
    print(f"{MOUNT_POINT} does not exist yet, creating...")
    os.mkdir(MOUNT_POINT)

if not os.path.isdir(MOUNT_POINT):
    print(f"{MOUNT_POINT} is not a directory, exiting...")
    sys.exit(1)

if ProjectedFS.PrjMarkDirectoryAsPlaceholder(MOUNT_POINT, None, None, instanceId) != S_OK:
    print(f"Error marking {MOUNT_POINT} directory as placeholder, exiting...")
    sys.exit(1)

print("Starting virtualization instance")

# Start Provider
instanceHandle = ProjectedFS.PRJ_NAMESPACE_VIRTUALIZATION_CONTEXT()
if ProjectedFS.PrjStartVirtualizing(MOUNT_POINT, callbackTable, None, None, instanceHandle) != S_OK:
    print("Error starting virtualization, exiting...")
    sys.exit(1)


input("Press any key to exit...\n")

# Stop Provider. MSDN says it returns an HRESULT, but the func prototype is void.
ProjectedFS.PrjStopVirtualizing(instanceHandle)
print("Stopped virtualization instance")

shutil.rmtree(MOUNT_POINT)
