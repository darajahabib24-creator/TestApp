# Kali Lab — GitHub Actions

Provisions a Kali Linux lab (Docker) with key-based SSH and an xrdp/XFCE desktop,
reachable over Tailscale. Reproduces the full method: image build, capability flags,
xrdp session manager + TLS, and auth-path verification.

```
.github/workflows/kali-lab.yml   # the workflow
kali/setup.sh                    # in-container provisioning (run as root)
kali/start.sh                    # container entrypoint
```

## 1. Configure secrets

In the repository: **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Value |
|---|---|
| `TAILSCALE_AUTH_KEY` | Auth key from the Tailscale admin console (API/Auth Keys). Tag it if your tailnet enforces tags; an **ephemeral** key is a good fit for CI. |
| `KALI_SSH_PUBKEY` | Your SSH **public** key (e.g. `~/.ssh/id_ed25519.pub`) that may log in as root. |

## 2. Run it

**Actions → Kali Lab → Run workflow**, choose:

- **runner** — `ubuntu-latest` for a throwaway build + verification, or a
  **self-hosted label** for a box that stays up after the run.
- **toolset** — `kali-linux-headless` (CLI), `kali-linux-default` (everything:
  Metasploit, Burp, …).
- **desktop** — `true` to install XFCE + xrdp.

## 3. Connect

The last step prints the details, e.g.:

```
ssh root@100.x.y.z -p 2222
RDP 100.x.y.z:3389   (user root)
```

Set the RDP password yourself over SSH (the pipeline never handles passwords):

```
ssh -p 2222 root@100.x.y.z
passwd
```

Then connect the Remote Desktop app to `100.x.y.z:3389`.

## Notes

- Ports are published bound to the **Tailscale IP only**, never `0.0.0.0`.
- `~/kali-data` is bind-mounted at `/root`, so your files survive recreation;
  installed packages live in the committed image `kalivm:ready`.
- The workflow verifies both paths: SSH key login, and the RDP auth chain
  (a deliberately wrong password must produce `AUTHFAIL` in `xrdp-sesman.log`).
- `--restart unless-stopped` keeps the container up across reboots on a self-hosted runner.
