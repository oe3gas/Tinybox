# Production version for the NanoPi

How to create a stripped production version of TinyBox for the NanoPi Core (512 MB RAM, 8 GB eMMC) and install it. Repeat these steps for every new revision.

## What goes into production

The NanoPi runs the full station ("PC2" setup):

| Part | Started by |
|---|---|
| TinyBox (`tinybox/`) | `tinybox.service` |
| brocastd, station mode (`brocast/brocast/`) | `brocastd.service` |
| GeoSphere weather (`geosphere_station.py`) | `geosphere-wetter.timer`, hourly at xx:05 |
| GeoSphere warnings (`geosphere_warnungen.py`) | `geosphere-warnungen.timer`, every 15 minutes |

Direwolf is not part of the build. Install and configure it separately (`AGWPORT 8000`, `KISSPORT 8001`).

**Included:**
- the `tinybox/` and `brocast/brocast/` packages, with their `web/` folders
- `brocast/brocast-core.yaml`
- the two GeoSphere scripts
- both `*.conf.example` templates
- `brocast/requirements.txt`
- `deploy/` (the systemd units and `install.sh`)
- a generated `VERSION` file

**Left out:**
- documentation and planning: `*.md`, `docs/`, `*.odt`
- tests: `tests/`, `brocast/tests/`, `brocast/test/`, `brocast/funktest/`
- `fwdsim/` (the forwarding simulator)
- `brocast/mockup/`
- old dictionary versions (`brocast-core.v*.yaml`) and `brocast.cddl`
- all Windows `*.bat` launchers

A build is about 0.8 MB, compared with 3.7 MB for the full repository.

## Files that drive the build

| File | Purpose |
|---|---|
| `build_production.sh` | Builds `production/<short-hash>/` from a git commit. Its `INCLUDE` list says what is shipped. |
| `deploy/install.sh` | Installs or updates the build on the NanoPi into `/opt/tinybox`. |
| `deploy/systemd/*` | The systemd units and timers that replace the `.bat` files and Windows scheduled tasks. |
| `deploy/journald-tinybox.conf` | Keeps the systemd journal in RAM only (16 MB). |
| `deploy/tmpfiles-tinybox.conf` | Creates the RAM folders under `/run/tinybox` at every boot and deletes old files in them. |

The existing program code is never changed for production.

## 1. Build a new production version

1. Commit everything that belongs in the release. The build reads files from the **commit** (`git archive`), not from the working tree, so uncommitted changes are never shipped.
2. Run the build:

   ```sh
   ./build_production.sh            # builds from HEAD
   ./build_production.sh 3547e37    # or from any other commit
   ```

   After a `production/...` commit, HEAD is that commit and not the code commit. In that case, always pass the source commit explicitly.

   The result is `production/<short-hash>/`, for example `production/f16d5a3/`. `VERSION` inside it records the full hash, the commit date and the build time.
3. Read the script's warnings:
   - **`WARNING: not classified (left out): <file>`** means a file was added that is in neither `INCLUDE` nor `EXCLUDE`. It was **not** shipped. Add it to `INCLUDE` if the NanoPi needs it at runtime, otherwise to `EXCLUDE`, then delete the build folder and build again.
   - **`deploy/ taken from the working tree`** means the `deploy/` files are not in that commit yet. That only happens for the first build, `f16d5a3`. Builds from later commits take `deploy/` from the commit.
4. Commit the new `production/<short-hash>/` folder. The commit that adds it has a different hash than the folder name. That is expected: the folder name is the hash of the **source** commit.

An existing build folder is never overwritten. To rebuild, delete it first.

## 2. Install on the NanoPi (first time)

Requirements: Debian or Armbian with systemd and Python 3.10 or newer. `install.sh` installs `python3-cbor2` and `python3-yaml` via apt if they are missing.

```sh
# on the PC
scp -r production/f16d5a3 nanopi:/tmp/
# on the NanoPi
sudo sh /tmp/f16d5a3/deploy/install.sh
```

The script does the following:
- creates the system user `tinybox` and copies the program to `/opt/tinybox`
- creates `tinybox.conf` and `brocast/brocastd.conf` from the templates
- installs and enables the units

On a first install it does **not** start the services. Edit the configuration first:

- `/opt/tinybox/tinybox.conf`: callsigns, sysop and `[chat_boards]`.
- `/opt/tinybox/brocast/brocastd.conf`: set `mode = station` (the template defaults to `listener`) and the callsign. brocastd won't start without a valid callsign.

The install also sets everything up to keep eMMC writes to a minimum. See [eMMC wear](#emmc-wear) for the details.

Then start everything:

```sh
sudo systemctl start brocastd tinybox geosphere-wetter.timer geosphere-warnungen.timer
```

Remove `/tmp/f16d5a3` afterwards.

## 3. Update to a newer version

Copy the new build folder and run its `install.sh` again. The script stops the services, replaces the program files and starts the services again.

It never overwrites these:
- `tinybox.conf` and `brocast/brocastd.conf`
- `brocast/brocast-core.yaml` (brocastd can update this itself through a dictionary import)
- `data/`, `brocast/data/`
- the GeoSphere state files

If a new version adds config options, compare your config with the new `*.conf.example` in `/opt/tinybox`.

The RAM paths in the configs are set only on the **first** install. On an existing device, set them by hand once (see [eMMC wear](#emmc-wear)).

To see what is installed: `cat /opt/tinybox/VERSION`.

## Operation

| Task | Command |
|---|---|
| Status | `systemctl status tinybox brocastd` and `systemctl list-timers 'geosphere*'` |
| Logs | `journalctl -u tinybox -f` (also `brocastd`, `geosphere-wetter`, `geosphere-warnungen`) |
| Restart | `sudo systemctl restart tinybox` |
| Sysop web login link | `journalctl -u tinybox \| grep "Web GUI"`, or use the token in `/opt/tinybox/data/web.token` |
| Web GUI from the PC | The GUI only listens on 127.0.0.1. Open a tunnel with `ssh -L 8080:127.0.0.1:8080 nanopi`, then browse to `http://127.0.0.1:8080/login?token=...` |
| Sysop console | There is no interactive console under systemd. Use the web GUI, or telnet with the sysop call: `ssh nanopi` then `telnet 127.0.0.1 6300` |

`SHUTDOWN` makes systemd restart TinyBox after 15 s, just like `tinybox_dauerbetrieb.bat` did. To stop it for good, run `sudo systemctl stop tinybox`.

The web GUI deliberately stays on 127.0.0.1, so it is never exposed on the LAN; use the SSH tunnel above. The login link contains the secret token and is written to the journal, which only root and the `adm` group can read. To invalidate it, delete `/opt/tinybox/data/web.token` and restart TinyBox.

## eMMC wear

The goal is to write to the eMMC only when real data changes. Reads don't wear the eMMC, so only writes matter. Everything transient lives in RAM (`/run` is tmpfs) and is gone after a reboot or power cut.

| What | Where | Set by |
|---|---|---|
| systemd journal (all program output) | RAM, max 16 MB (`Storage=volatile`) | `deploy/journald-tinybox.conf` |
| brocastd program log | journal only (`log_dir` empty) | `brocastd.conf`, first install |
| Sendeprotokoll | `/run/tinybox/sendeprotokoll`, files older than 7 days deleted | `txlog_dir` in `brocastd.conf`, first install |
| Inbox (GeoSphere → TinyBox) | `/run/tinybox/eingang`. `erledigt/` is cleaned after 2 days, `fehler/` after 7 days | `[inbox] dir` in `tinybox.conf` (first install) and `--tinybox` in the geosphere units. Both must match. |
| Python bytecode | precompiled once by `install.sh`, never written at runtime | `PYTHONDONTWRITEBYTECODE=1` in the units |
| TinyBox mail database | **eMMC**. It holds mail and must survive power cuts. It is written only on logins, messages and chat. | – |
| brocastd database | **eMMC**, but it currently writes on every radio frame. See **PLANUNG.md, open point 9 / P1 (major fix)**. | – |
| GeoSphere warning state | eMMC, a tiny file written only when the warnings change | – |

To switch a device that was installed earlier, set these by hand:
- In `tinybox.conf`, under `[inbox]`, set `dir = /run/tinybox/eingang`.
- In `brocastd.conf`, set `log_dir =` (empty) and `txlog_dir = /run/tinybox/sendeprotokoll`.
- Run `install.sh` again to install the units, the tmpfiles and the journald files.

System settings are outside `install.sh`, which only prints hints:
- Mount the root filesystem with `noatime`.
- Use no swap on the eMMC. zram is fine.
- On Armbian, `armbian-ramlog` already keeps `/var/log` in RAM.

The journal is in RAM, so logs from before a crash or reboot are lost. To keep them for troubleshooting, temporarily set `Storage=persistent` in `/etc/systemd/journald.conf.d/tinybox.conf` and run `systemctl restart systemd-journald`.

## Checklist for each revision

- [ ] Everything committed, tests pass on the development machine
- [ ] `./build_production.sh` runs with no `not classified` warnings
- [ ] Commit `production/<short-hash>/`
- [ ] Copy it to the NanoPi and run `sudo sh deploy/install.sh`
- [ ] Check `systemctl status tinybox brocastd` and `journalctl -u tinybox -n 30`
