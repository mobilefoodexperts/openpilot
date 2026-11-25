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

## Known limits

- PitStop only sends CAN messages while the car is off (`selfdrive/controls/lib/can_api/handler.py`), so it can never compete with `card` for `sendcan` while driving.
- The fork's static model `.pkl` self-heal and `chestnut_link.py` were removed in Nov 2026: sunnypilot removed model chunking (#38941), and they would have made every update fail.
- PitStop's Chestnut flash/overheat and model-provisioning cards show empty, because nothing writes those params any more.
