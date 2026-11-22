#!/bin/sh
# Container entrypoint: start the xrdp session manager + server, then sshd.
set -e
mkdir -p /run/sshd /run/xrdp/sockdir

# Clear stale runtime state. If an image was committed while xrdp was running,
# /var/run/xrdp/*.pid makes sesman think it is already running, so RDP shows the
# login screen and then fails with "Error connecting to sesman".
rm -f /var/run/xrdp/*.pid /run/xrdp/sockdir/*.lock

/etc/init.d/xrdp start >/dev/null 2>&1 || true
exec /usr/sbin/sshd -D -e
