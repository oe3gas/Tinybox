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

The existing program code is never changed for production.

## 1. Build a new production version

1. Commit everything that belongs in the release. The build reads files from the **commit** (`git archive`), not from the working tree, so uncommitted changes are never shipped.
2. Run the build:

   ```sh
   ./build_production.sh            # builds from HEAD
   ./build_production.sh 3547e37    # or from any other commit
   ```

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
- `/opt/tinybox/brocast/brocastd.conf`:
  - set `mode = station` (the template defaults to `listener`) and the callsign
  - recommended: `log_dir =` (empty). systemd already writes the program output to the journal, so the extra log file only adds eMMC writes.

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
- `data/`, `brocast/data/`, `eingang/`, `logs/`
- the GeoSphere state files

If a new version adds config options, compare your config with the new `*.conf.example` in `/opt/tinybox`.

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

**Keep the eMMC healthy.** Limit the journal size in `/etc/systemd/journald.conf`, for example with `SystemMaxUse=50M`.

## Checklist for each revision

- [ ] Everything committed, tests pass on the development machine
- [ ] `./build_production.sh` runs with no `not classified` warnings
- [ ] Commit `production/<short-hash>/`
- [ ] Copy it to the NanoPi and run `sudo sh deploy/install.sh`
- [ ] Check `systemctl status tinybox brocastd` and `journalctl -u tinybox -n 30`
