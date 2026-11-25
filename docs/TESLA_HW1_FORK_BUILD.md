# Tesla HW1 fork: build and update checklist

How this fork (`mobilefoodexperts/openpilot`, branch `sunnypilot-nov-2026` and later) is kept current with sunnypilot, and what must stay true so a **comma 4** can install it.

## Where things live

| Piece | Repo / branch |
|---|---|
| openpilot + sunnypilot + fork features (PitStop, `op fork`) | `mobilefoodexperts/openpilot` |
| Tesla HW1 car code and safety (`opendbc_repo` submodule) | `mobilefoodexperts/opendbc` |
| Original HW1 fork this is based on | `P6g9YHK6/SunnyPilot-TeslaHW1` (`dev`), `P6g9YHK6/opendbc` |
| Upstream | `sunnypilot/sunnypilot` `master`, `sunnypilot/opendbc` `master` |
| Driving model lists | `sunnypilot/sunnypilot-models` `gh-pages/docs/driving_models_v*.json` |

The HW1 changes that must survive every update are listed in `opendbc/car/tesla/imports_to_maintain.md` in the opendbc repo.

## Rules a branch must meet to install on a comma 4

1. **The GitHub repo must be named `openpilot`.** The comma's "install custom software" screen sends `user/branch` to installer.comma.ai, which clones `github.com/<user>/openpilot.git`. Any other repo name returns "not compatible with this device".
2. **Branch name:** don't end it in `-tici` (that is the comma 3 channel). `release3` and `release3-staging` are renamed by the installer; any other name is fine.
3. **Every submodule commit must be pushed and public** (`.gitmodules`: opendbc → `mobilefoodexperts/opendbc`, panda → `sunnyhaibin/panda`, tinygrad, msgq, rednose, teleoprtc, neural_network_data). The installer clones with `--recurse-submodules` and stops on any failure.
4. **`uv.lock` must match `pyproject.toml`.** The device runs `uv sync --frozen --all-extras`, which installs exactly the lockfile and silently skips anything not in it. After any dependency change run `uv lock`, then `uv lock --check`. (PitStop needs `aiohttp`; sunnypilot itself no longer does, so a merge that takes upstream's lock drops it.)
5. **Git LFS:** `.lfsconfig` must be sunnypilot's (`huggingface.co/sunnypilot/sunnypilot-lfs`). Every LFS file in the branch must already exist there; check with `git lfs ls-files -l HEAD` vs `upstream/master`. The fork adds no LFS files of its own; keep it that way (store new fork images as normal files). Push with `GIT_LFS_SKIP_PUSH=1` (we can't write to that store).
6. **AGNOS:** `launch_env.sh` `AGNOS_VERSION` and `openpilot/common/hardware/comma/agnos.json` come from upstream together; the device updates its OS on first boot if they differ from `/VERSION`.
7. **No `prebuilt` file** in a source branch, so the device builds with SCons on first boot.
8. **Symlinks stay symlinks.** On Windows set `core.symlinks=false` only for reading; check `git ls-tree -r HEAD | awk '$1=="120000"'` before pushing.

## Updating to newer sunnypilot (the method that works)

The fork's history isn't linked to sunnypilot's by real merges, so a plain `git merge` sees no common base. Use a three-way merge with an explicit base:

1. Note the sunnypilot commit the fork last synced to (`BASE`). The Nov 2026 build merged sunnypilot master `6732fcc52`, so that is `BASE` for the next update (that build itself used `94ed0608e`).
2. `git commit-tree <fork-tree> -p BASE -p <fork-head>` to make a commit that sits on top of `BASE`, check it out, then `git merge upstream/master` (fetch with `--shallow-since` a few days before `BASE` so git can see the base).
3. Conflict policy:
   - Model code (`selfdrive/modeld`, `sunnypilot/modeld_v2`, `sunnypilot/models`, chestnut, model UI), tinygrad, panda, AGNOS, CI, tools: take **sunnypilot's**. Models are compiled for a specific tinygrad and selector version; mixing breaks them.
   - `opendbc_repo`: merge `sunnypilot/opendbc` into `mobilefoodexperts/opendbc` first (keep `tesla_legacy.h`, HW1 ignition in `safety/ignition.h`, HW1 platforms in `car/tesla/values.py`), push, then pin that commit.
   - Fork features (PitStop toggle and params, `op fork`, venv self-heal in `updated.py`): keep, and re-check that their imports still exist upstream.
4. Commit the merged tree onto the fork's previous branch head (single parent) and push.
5. Check: model URLs in `sunnypilot/models/fetcher.py` and `REQUIRED_JSON_VERSION` in `sunnypilot/models/helpers.py` match sunnypilot's; `uv lock --check`; no conflict markers; every `openpilot.*` import in fork code resolves; Tesla tests in opendbc (`pytest opendbc/car/tesla/tests`, Python 3.12).

## Prebuilt branch (faster install)

A `-prebuilt` branch has everything already compiled, so the comma skips the long build on install. The driving models are compiled for the comma's own GPU, so a prebuilt can only be made **on a comma** (sunnypilot does the same with its own devices; the original fork's GitHub-runner workflow relied on model files copied from a device and broke whenever tinygrad changed, so it was not carried over).

1. Install the source branch on the comma and confirm it builds and drives.
2. Enable SSH on the comma (Settings → Developer → SSH keys: a GitHub username whose keys include the PC's key).
3. Over SSH, stop openpilot, then run the steps at the top of `tools/release/build_fork_prebuilt.sh` with `PREBUILT_BRANCH=<branch>-prebuilt`.
4. From the PC: `git fetch ssh://comma@<ip>/data/src_openpilot <branch>-prebuilt:<branch>-prebuilt`, then `GIT_LFS_SKIP_PUSH=1 git push origin <branch>-prebuilt` (the prebuilt has no LFS: binaries are committed as plain files).
5. Reinstall the comma from `mobilefoodexperts/<branch>-prebuilt` (also the URL to give anyone else).

Rebuild the prebuilt after every change to the source branch.

## sunnylink

The fork doesn't change any sunnylink code, params or processes, and nothing checks the repo or branch, so sunnylink works the same as on sunnypilot: the device is identified by its keys and dongle ID. After install:

1. Connect to Wi-Fi and let the comma dongle ID register.
2. **Settings → sunnylink:** enable sunnylink, accept the consent screen, wait for a sunnylink dongle ID.
3. **Pair** (QR code) to link a GitHub account; sponsoring is optional. Basic backup/restore doesn't need a sponsor tier.
4. **Back up settings** right away (restore works only on the same device).
5. **Changing the model from the app:** sunnylink can write the model-download request (`ModelManager_DownloadRef`, not on the blocked list in `sunnypilot/sunnylink/athena/sunnylinkd.py`), and sunnypilot advertises the model selector in the sunnylink dashboard. The device downloads and switches only while the car is off. The on-device Settings → Models page always works.

## Testing on a Linux PC (external Ubuntu SSD)

Use **Ubuntu 24.04 LTS Desktop** (sunnypilot's CI runs on `ubuntu-24.04`; Python 3.12). Give it 40 GB+ and install the NVIDIA drivers for the simulator.

```bash
git clone --recurse-submodules -b sunnypilot-nov-2026 https://github.com/mobilefoodexperts/openpilot.git
cd openpilot
tools/op.sh setup          # installs uv, Python deps, system packages
source .venv/bin/activate
scons -j$(nproc)           # build for PC
```

- **comma 4 UI on the PC** (check screen/icon changes without the car): see `openpilot/selfdrive/ui/tests/` and the UI report the GitHub test run uploads (`ui-report-*` artifact).
- **Replay a recorded drive** (needs drives from the comma): `openpilot/tools/replay/`.
- **Driving simulator** (MetaDrive): `openpilot/tools/sim/README.md`.
- **Tests:** `pytest openpilot/selfdrive/car/tests/test_car_interfaces.py -k TESLA` and, in `opendbc_repo`, `pytest opendbc/car/tesla/tests`.

## From the sunnypilot community forum (read Nov 25 2026)

Nothing on community.sunnypilot.ai covers HW1/AP1 S/X; these are the general lessons that apply.

**Install / update**
- Switch branches by **uninstall + reinstall**, not the updater: 2026.003 moved the tree under `openpilot/` and older updaters can get stuck (t/6495, t/3844).
- If an install stalls (~10%) or says "incompatible": install stock openpilot first, let it boot, uninstall, then install this branch (t/3722, t/6084). If another fork changed AGNOS, reflash at flash.comma.ai first (t/5732, t/5452).
- `openpilot failed to build ... scons_cache lock`: power dropped mid-build; clear `/data/scons_cache` or factory reset (t/2227).
- Power the comma from the car or a USB-PD brick during install; a PC USB port isn't enough (t/2099).

**Power / offroad**
- Set **Max Offroad Time** short (5-30 min; minutes; needs "Show Advanced Controls"). A Tesla owner tripped the Autopilot computer eFuse with a 30 h stay-on (t/2865). It is ignored while the comma sees ignition (`power_monitoring.py`: `should_shutdown &= not ignition`), so check the 0x201 note below on the first park.
- The comma shuts down below ~11.8 V car battery - an early sign of a weak 12 V battery (t/973).
- A maintainer-confirmed bug once treated message 0x201 as ignition and kept devices from going offroad (t/4612, fixed upstream). This fork's own `ignition.h` rule treats 0x201 (SDM1 on HW1) as ignition on.

**sunnylink**
- Never "unpair"/delete the device in sunnylink (irreversible; backups lost) (t/1944, t/5651). Note the sunnylink dongle ID after pairing.
- Fork-added params show up under "Other" automatically (t/3164). Settings pushed from sunnylink may need an offroad/onroad cycle (t/5400).
- Models can be switched from sunnylink.ai/dashboard/models or on the device; after updates check the active model didn't revert to the default (t/7525).

**Models (Tesla = angle steering; torque tuning / NNLC don't apply, t/3124)**
- Baseline: **CD210** (default). Users with angle-steering cars and Teslas report good results with SC Model, Cheddar (with Blendful), RDF (staging/dev only); OP Model 7/8/10v1 and WMIv12 ping-pong on angle cars (t/2305, t/7723, t/6569, t/4317).
- Change one thing at a time; don't reset calibration between model comparisons (t/4393). Camera offset max ±0.35 m (t/2312).

**Rules for forks** (comma/sunnypilot): never weaken panda/opendbc safety or driver monitoring; keep the opendbc safety test suite passing or risk a fork/device ban (t/381, t/253). `tesla_legacy.h` (from the original fork) currently fails opendbc's MISRA check - style only, but worth fixing.

## Known limits

- `updated.py` `sync_venv()` builds a **relocatable** `.venv` in the staging dir (a default uv venv hard-codes its path and breaks when the update is moved into place) and never fails an update: if uv is missing or the sync fails it removes `.venv`, and `launch_chffrplus.sh` uses AGNOS's `/usr/local/venv` like upstream. On a fresh install there is no `.venv`, so PitStop (needs `aiohttp`) may not start until the first update.
- PitStop runs on port 8082 (copyparty owns 8080; :80 still redirects to PitStop), creates `/data/pitstop` itself, and starts through `pitstop/launcher.py`, which idles instead of crash-looping if PitStop can't start. It refuses every change (settings, backup restore, reboot, CAN send) unless `IsOffroad` is set, because it has no login and anyone on the same Wi-Fi can reach it.
- Legacy Model S/X (HW1-3) report **no blind-spot sensors** (`has_bsm` in opendbc's `sunnypilot/car/interfaces.py`): `update_legacy` never fills blind-spot data, so BSM-gated lane-change features stay off.
- To confirm on the car: `safety/ignition.h` treats any `0x201` frame on bus 0/2 as ignition on (from the original fork). If HW1 sends 0x201 while parked, the comma would never go offroad (no updates, 12 V drain).
- PitStop only sends CAN messages while the car is off (`selfdrive/controls/lib/can_api/handler.py`), so it can never compete with `card` for `sendcan` while driving.
- The fork's static model `.pkl` self-heal and `chestnut_link.py` were removed in Nov 2026: sunnypilot removed model chunking (#38941), and they would have made every update fail.
- PitStop's Chestnut flash/overheat and model-provisioning cards show empty, because nothing writes those params any more.
