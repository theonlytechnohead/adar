import os
import errno

from fuse import FUSE, FuseOSError, Operations

import storage_backing
import storage_sync

from constants import *
from peers import *


class Storage(Operations):
    def __init__(self, root):
        self.root = root
        self.handles: dict[int, str] = {}

    # Helpers
    # =======

    def _root_path(self, path):
        if path.startswith("/"):
            path = path[1:]
        path = os.path.join(self.root, path)
        return path

    # Filesystem methods
    # ==================

    def access(self, path, mode):
        root_path = self._root_path(path)
        if not os.access(root_path, mode):
            raise FuseOSError(errno.EACCES)

    def chmod(self, path, mode):
        root_path = self._root_path(path)
        return os.chmod(root_path, mode)

    def chown(self, path, uid, gid):
        root_path = self._root_path(path)
        return os.chown(root_path, uid, gid)

    def getattr(self, path, fh=None):
        root_path = self._root_path(path)
        st = os.lstat(root_path)
        return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime',
                     'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))

    def readdir(self, path, fh):
        root_path = self._root_path(path)

        dirents = ['.', '..']
        if os.path.isdir(root_path):
            dirents.extend(os.listdir(root_path))
        for r in dirents:
            yield r

    def readlink(self, path):
        pathname = os.readlink(self._root_path(path))
        if pathname.startswith("/"):
            # Path name is absolute, sanitize it.
            return os.path.relpath(pathname, self.root)
        else:
            return pathname

    def mknod(self, path, mode, dev):
        return os.mknod(self._root_path(path), mode, dev)

    def rmdir(self, path):
        result = storage_backing.remove(path)
        storage_sync.remove(path)
        return result

    def mkdir(self, path, mode):
        result = storage_backing.create(path, True, mode=mode)
        storage_sync.create(path, True)
        return result

    def statfs(self, path):
        root_path = self._root_path(path)
        stv = os.statvfs(root_path)
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
            'f_frsize', 'f_namemax'))

    def unlink(self, path):
        result = storage_backing.remove(path)
        storage_sync.remove(path)
        return result

    def symlink(self, name, target):
        return os.symlink(name, self._root_path(target))

    def rename(self, old, new):
        result = storage_backing.rename(old, new)
        storage_sync.rename(old, new)
        return result

    def link(self, target, name):
        return os.link(self._root_path(target), self._root_path(name))

    def utimens(self, path, times=None):
        return os.utime(self._root_path(path), times)

    # File methods
    # ============

    def open(self, path, flags):
        root_path = self._root_path(path)
        handle = os.open(root_path, flags)
        self.handles[handle] = path
        return handle

    def create(self, path, mode, fi=None):
        result = storage_backing.create(path, False, mode=mode)
        storage_sync.create(path, False)
        self.handles[result] = path
        return result

    def read(self, path, length, offset, fh):
        file_path = self.handles[fh]
        result = storage_backing.read_file(file_path, offset, length, handle=fh)
        # data = storage_sync.read(file_path, offset, length)
        return result

    def write(self, path, buf, offset, fh):
        file_path = self.handles[fh]
        result = storage_backing.write(file_path, offset, len(buf), buf, handle=fh)
        storage_sync.write(file_path, offset, buf)
        return result

    def truncate(self, path, length, fh=None):
        root_path = self._root_path(path)
        with open(root_path, 'r+') as f:
            f.truncate(length)

    def flush(self, path, fh):
        return os.fsync(fh)

    def release(self, path, fh):
        del self.handles[fh]
        return os.close(fh)

    def fsync(self, path, fdatasync, fh):
        return self.flush(path, fh)

def create():
    destroy()
    if not os.path.exists(ROOT_POINT):
        os.mkdir(ROOT_POINT)
    if not os.path.exists(MOUNT_POINT):
        os.mkdir(MOUNT_POINT)
    FUSE(Storage(ROOT_POINT), MOUNT_POINT, foreground=True)


def destroy():
    os.system(f"fusermount -u {MOUNT_POINT} > /dev/null 2>&1")
    if os.path.exists(MOUNT_POINT):
        os.rmdir(MOUNT_POINT)
