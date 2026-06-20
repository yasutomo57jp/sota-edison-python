#!/usr/bin/env -S uv run --with paramiko --quiet python3
import sys, paramiko
host = sys.argv[1]
cmd  = sys.argv[2]
user = sys.argv[3] if len(sys.argv) > 3 else "root"
pw   = sys.argv[4] if len(sys.argv) > 4 else "edison00"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(host, username=user, password=pw, timeout=12, look_for_keys=False, allow_agent=False)
stdin, stdout, stderr = c.exec_command(cmd, timeout=30)
out = stdout.read().decode("utf-8", "replace")
err = stderr.read().decode("utf-8", "replace")
sys.stdout.write(out)
if err.strip():
    sys.stderr.write("\n[stderr]\n" + err)
c.close()
