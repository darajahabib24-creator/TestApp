#!/bin/bash
# Runs INSIDE the Kali container as root.
# Installs the toolset, configures key-only SSH, and (optionally) an xrdp/XFCE desktop.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

TOOLSET="${TOOLSET:-kali-linux-headless}"
ENABLE_DESKTOP="${ENABLE_DESKTOP:-true}"

echo "[setup] apt update"
apt-get update -qq

echo "[setup] installing toolset: ${TOOLSET}"
apt-get install -y --no-install-recommends "$TOOLSET" openssh-server sudo

# --- SSH: key-only root login ---------------------------------------------
sed -i -E 's/^#?PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
sed -i -E 's/^#?PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config
sed -i -E 's/^#?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config

# authorized_keys is bind-mounted from the host; fix ownership so sshd's
# StrictModes accepts it.
install -d -m 700 /root/.ssh
chmod 700 /root/.ssh
chmod 600 /root/.ssh/authorized_keys
chown -R root:root /root/.ssh
/usr/sbin/sshd -t

# --- Desktop + RDP --------------------------------------------------------
if [ "$ENABLE_DESKTOP" = "true" ]; then
  echo "[setup] installing XFCE + xrdp + X server"
  apt-get install -y --no-install-recommends \
    kali-desktop-xfce xrdp xorgxrdp xserver-xorg-core openssl

  # Dedicated TLS cert owned by the xrdp group; the default symlinks into
  # /etc/ssl/private are unreadable by the xrdp user and force classic RDP.
  rm -f /etc/xrdp/cert.pem /etc/xrdp/key.pem
  openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout /etc/xrdp/key.pem -out /etc/xrdp/cert.pem \
    -days 3650 -subj "/CN=kalivm" 2>/dev/null
  chown root:xrdp /etc/xrdp/key.pem /etc/xrdp/cert.pem
  chmod 640 /etc/xrdp/key.pem
  chmod 644 /etc/xrdp/cert.pem
fi

echo "[setup] done"
