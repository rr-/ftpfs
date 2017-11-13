ftpfs
-----

I needed to `rsync` something into an FTP server and `curlftpfs`, the only
FTP over FUSE implementation I know of, has [failed me
completely](https://bugs.launchpad.net/ubuntu/+source/curlftpfs/+bug/888153).

Highlights:

- Worked for me once so it must be completely bug-free
- I'll ~~fix bugs you encounter~~ implement features you need
  if you provide me with a test FTP server
- No symlinks support

License - [MIT](LICENSE.md).
