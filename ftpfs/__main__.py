#!/usr/bin/env python3
import time
import datetime
import argparse
import os
import sys
import stat
import tempfile
import errno
from getpass import getpass
from ftplib import FTP
from fuse import FUSE, FuseOSError, Operations  # fusepy


DEFAULT_DATE = '19700101000000'


def debug(*args):
    print(*args)


def convert_time(src):
    parsed = datetime.datetime.strptime(src, '%Y%m%d%H%M%S')
    return time.mktime(parsed.timetuple())


def convert_perm(src):
    ret = 0
    if 'a' in src:
        # file, can be appended to
        ret |= stat.S_IFREG
    if 'c' in src:
        # directory
        ret |= stat.S_IFDIR
    if 'd' in src:
        # anything, can be deleted
        pass
    if 'e' in src:
        # directory, can be traversed into
        ret |= stat.S_IFDIR | 0o111
    if 'f' in src:
        # anything, can be renamed
        pass
    if 'l' in src:
        # directory, can be listed
        ret |= stat.S_IFDIR | 0o444
    if 'm' in src:
        # directory, can create new directories inside
        ret |= stat.S_IFDIR | 0o200
    if 'p' in src:
        # directory, can remove directories inside
        ret |= stat.S_IFDIR | 0o200
    if 'r' in src:
        # file, can be read
        ret |= stat.S_IFREG | 0o444
    if 'w' in src:
        # file, can be written to
        ret |= stat.S_IFREG | 0o200
    return ret


class FTPFS(Operations):
    def __init__(self, ftp):
        self._ftp = ftp
        self._dir_cache = {}
        self._file_cache = {}
        self._file_handles = {}

    def access(self, path, mode):
        debug('access', path, mode)
        raise FuseOSError(errno.ENOSYS)

    def getattr(self, path, fh=None):
        debug('getattr', path)
        try:
            file_info = self._file_cache[path]
        except KeyError:
            list(self.readdir(os.path.dirname(path), None))
            try:
                file_info = self._file_cache[path]
            except KeyError:
                raise FuseOSError(errno.ENOENT)

        perm = convert_perm(file_info['perm'])
        if 'unix.mode' in file_info:
            perm &= ~0o777
            perm |= int(file_info['unix.mode'], 8)

        ret = {
            'st_atime': int(
                convert_time(file_info.get('modify', DEFAULT_DATE))),
            'st_mtime': int(
                convert_time(file_info.get('modify', DEFAULT_DATE))),
            'st_ctime': int(
                convert_time(
                    file_info.get(
                        'create',
                        file_info.get('modify', DEFAULT_DATE)))),
            'st_gid': int(file_info.get('unix.group', '0')),
            'st_uid': int(file_info.get('unix.owner', '0')),
            'st_mode': perm,
            'st_size': int(file_info.get('size', 0)),
            'st_nlink': 0,
        }
        return ret

    def readdir(self, path, fh):
        debug('readdir', path, fh)
        self._ftp.cwd(path)
        if path not in self._dir_cache:
            self._dir_cache[path] = list(self._ftp.mlsd())
            for item, data in self._dir_cache[path]:
                if item == '..':
                    continue
                if item == '.':
                    item_path = path
                else:
                    item_path = os.path.join(path, item)
                self._file_cache[item_path] = data

        for item, data in self._dir_cache[path]:
            yield item

    def chmod(self, path, mode):
        debug('chmod', path, mode)
        self._ftp.sendcmd(f'SITE CHMOD {mode & 0o777:3o} {path}')
        self._wipe_cache()

    def chown(self, path, uid, gid):
        debug('chown', path, uid, gid)
        raise FuseOSError(errno.ENOSYS)

    def readlink(self, path):
        debug('readlink', path)
        raise FuseOSError(errno.ENOSYS)

    def symlink(self, name, target):
        debug('symlink', name, target)
        raise FuseOSError(errno.ENOSYS)

    def mknod(self, path, mode, dev):
        debug('mknod', path, mode, dev)
        raise FuseOSError(errno.ENOSYS)

    def mkdir(self, path, mode):
        debug('mkdir', path, mode)
        self._ftp.mkd(path)
        self._wipe_cache()

    def rmdir(self, path):
        debug('rmdir', path)
        self._ftp.rmd(path)
        self._wipe_cache()

    def statfs(self, path):
        debug('statfs', path)
        raise FuseOSError(errno.ENOSYS)

    def unlink(self, path):
        debug('unlink', path)
        self._ftp.delete(path)
        self._wipe_cache()

    def rename(self, old, new):
        debug('rename', old, new)
        self._ftp.rename(old, new)
        self._wipe_cache()

    def utimens(self, path, times=None):
        debug('utimens', path, times)
        raise FuseOSError(errno.ENOSYS)

    def open(self, path, flags):
        debug('open', path, flags)
        handle = tempfile.SpooledTemporaryFile()
        self._file_handles[self._path_to_fd(path)] = handle
        self._ftp.retrbinary('RETR ' + path, handle.write)
        return self._path_to_fd(path)

    def create(self, path, mode, fi=None):
        debug('create', path, mode, fi)
        handle = tempfile.SpooledTemporaryFile()
        self._file_handles[self._path_to_fd(path)] = handle
        self._ftp.storbinary('STOR ' + path, handle)
        self._wipe_cache()
        return self._path_to_fd(path)

    def read(self, path, length, offset, fh):
        debug('read', path, length, offset, fh)
        self._file_handles[self._path_to_fd(path)].seek(offset)
        return self._file_handles[self._path_to_fd(path)].read(length)

    def write(self, path, buf, offset, fh):
        debug('write', path, buf, offset, fh)
        handle = self._file_handles[self._path_to_fd(path)]
        handle.seek(offset)
        return handle.write(buf)

    def truncate(self, path, length, fh=None):
        debug('truncate', path, length, fh)
        handle = self._file_handles[self._path_to_fd(path)]
        handle.truncate(length)
        handle.flush()

    def flush(self, path, fh):
        debug('flush', path, fh)
        self._file_handles[self._path_to_fd(path)].flush()
        self._wipe_cache()

    def release(self, path, fh):
        debug('release', path, fh)
        handle = self._file_handles[self._path_to_fd(path)]
        handle.seek(0)
        self._ftp.storbinary('STOR ' + path, handle)
        handle.close()
        del self._file_handles[self._path_to_fd(path)]
        self._wipe_cache()

    def fsync(self, path, fdatasync, fh):
        return self.flush(path, fh)

    def _path_to_fd(self, path):
        return hash(path)

    def _wipe_cache(self):
        self._dir_cache = {}
        self._file_cache = {}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('host')
    parser.add_argument('dest')
    parser.add_argument('--user')
    parser.add_argument('--pass', '--password', dest='password')
    parser.add_argument('-d', '--daemon', action='store_true')
    ret = parser.parse_args()
    if not ret.user:
        ret.user = input('User: ')
    if not ret.password:
        ret.password = getpass('Password: ')
    return ret


def main():
    args = parse_args()
    ftp = FTP(host=args.host, user=args.user, passwd=args.password)
    FUSE(FTPFS(ftp), args.dest, nothreads=True, foreground=not args.daemon)


if __name__ == '__main__':
    main()
