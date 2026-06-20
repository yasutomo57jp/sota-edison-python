#!/usr/bin/env python3
import sys, paramiko
host, remote, local = sys.argv[1], sys.argv[2], sys.argv[3]
user = sys.argv[4] if len(sys.argv) > 4 else "root"
pw   = sys.argv[5] if len(sys.argv) > 5 else "edison00"
t = paramiko.Transport((host, 22))
t.connect(username=user, password=pw)
sftp = paramiko.SFTPClient.from_transport(t)
sftp.get(remote, local)
sftp.close(); t.close()
print("downloaded", remote, "->", local)
