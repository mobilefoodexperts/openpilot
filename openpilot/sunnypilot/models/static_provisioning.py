"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""

# Self-heal for the static model files of a staged update, called by
# openpilot/system/updated/updated.py while finalizing it (the car still runs the old
# checkout). Kept from the Tesla HW1 fork and ported to sunnypilot Nov 2026:
#
# - The fork's version downloaded "chunked" .pkl files from Hugging Face manifests. sunnypilot
#   removed chunking (#38941): the default and chestnut ("big") model .pkl files now come with
#   the git tree through Git LFS, and the small/dm models are compiled by SCons at boot.
# - What can still go wrong is the LFS download: a model file left as an LFS pointer (text)
#   instead of the real weights makes modeld crash on every drive. This checks every tracked
#   model .pkl, re-runs `git lfs pull` for broken ones, and fails the update if they stay
#   broken ("fail the update, not the car": the next update attempt retries).
# - While the car is off, it also test-loads the tracked driving .pkl files with the new
#   checkout's own tinygrad, like the fork did. A failed load is recorded, not fatal: the big
#   model is optional (modeld falls back to the small one).
#
# The result goes to the ModelStaticProvisioningStatus param, shown by PitStop.

import json
import os
import subprocess
import time
from pathlib import Path

from openpilot.common.params import Params
from openpilot.common.swaglog import cloudlog

MODEL_DIRS = ("openpilot/selfdrive/modeld/models", "openpilot/sunnypilot/modeld_v2/models")
LFS_POINTER_PREFIX = b"version https://git-lfs"
DRIVING_PKLS = ("driving_tinygrad.pkl", "big_driving_tinygrad.pkl")
LFS_PULL_TIMEOUT = 30 * 60
LOAD_TIMEOUT = 120

# keys modeld.ModelState reads from a driving pkl (openpilot/selfdrive/modeld/modeld.py)
_LOAD_DRIVING = ("import sys; from openpilot.selfdrive.modeld.helpers import load_oob; " +
                 "j = load_oob(sys.argv[1], sys.argv[2] == '1'); " +
                 "missing = [k for k in ('input_specs', 'output_specs', 'metadata', 'run') if k not in j]; " +
                 "assert not missing, f'incompatible driving pkl, missing keys {missing}'")

# tinygrad's AMD/USB backend errors when the chestnut isn't linked: a hardware problem, not a bad file
_HARDWARE_UNAVAILABLE_MARKERS = (
  "PCIe link not up", "No interface for", "no pcie", "/dev/kfd", "chestnut did not enumerate",
)


class ModelProvisioningError(Exception):
  pass


def _tracked_model_files(checkout_dir: str) -> list[str]:
  out = subprocess.check_output(["git", "ls-files", "-z", "--", *MODEL_DIRS], cwd=checkout_dir, timeout=60)
  return [f for f in out.decode("utf8").split("\0") if f.endswith(".pkl")]


def file_status(path: Path) -> str:
  """'ok', 'missing', or 'lfs_pointer' (the LFS download didn't happen)."""
  if not path.is_file() or path.stat().st_size == 0:
    return "missing"
  with open(path, "rb") as f:
    if f.read(len(LFS_POINTER_PREFIX)) == LFS_POINTER_PREFIX:
      return "lfs_pointer"
  return "ok"


def _lfs_pull(checkout_dir: str, rel_paths: list[str]) -> None:
  try:
    subprocess.run(["git", "lfs", "pull", f"--include={','.join(rel_paths)}"], cwd=checkout_dir,
                   check=True, capture_output=True, timeout=LFS_PULL_TIMEOUT)
  except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
    stderr = getattr(e, "stderr", b"") or b""
    cloudlog.error(f"git lfs pull failed for {rel_paths}: {e} {stderr.decode('utf8', errors='replace')}")


def _python_for(checkout_dir: str) -> str | None:
  for python in (os.path.join(checkout_dir, ".venv", "bin", "python3"), "/usr/local/venv/bin/python3"):
    if os.path.isfile(python):
      return python
  return None


def try_load(checkout_dir: str, rel_path: str) -> str:
  """'ok', 'failed' or 'hardware_unavailable'. Loads in a subprocess with the checkout's own
  code and tinygrad pin, so a bad pickle can't crash the updater."""
  python = _python_for(checkout_dir)
  if python is None:
    return "skipped"
  chestnut = Path(rel_path).name.startswith("big_")
  env = {**os.environ, "PYTHONPATH": f"{checkout_dir}:{os.path.join(checkout_dir, 'tinygrad_repo')}"}
  try:
    subprocess.run([python, "-c", _LOAD_DRIVING, rel_path, "1" if chestnut else "0"], cwd=checkout_dir, env=env,
                   check=True, capture_output=True, timeout=LOAD_TIMEOUT)
    return "ok"
  except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
    stderr = getattr(e, "stderr", b"") or b""
    text = stderr.decode("utf8", errors="replace") if isinstance(stderr, bytes) else str(stderr)
    if chestnut and any(marker in text for marker in _HARDWARE_UNAVAILABLE_MARKERS):
      cloudlog.warning(f"{rel_path}: chestnut not available, skipping load check")
      return "hardware_unavailable"
    cloudlog.warning(f"model load check failed for {rel_path}: {e} {text[-2000:]}")
    return "failed"


def verify_and_refresh_static_models(checkout_dir: str, chestnut: bool = False, load_check: bool = True) -> dict[str, str]:
  """Raises ModelProvisioningError if a tracked model file is still missing or an LFS pointer
  after one `git lfs pull`; the caller must then not mark the update ready."""
  rel_paths = _tracked_model_files(checkout_dir)
  outcomes = {p: file_status(Path(checkout_dir) / p) for p in rel_paths}

  broken = [p for p, s in outcomes.items() if s != "ok"]
  if broken:
    cloudlog.warning(f"model files not downloaded in update, pulling from LFS: {broken}")
    _lfs_pull(checkout_dir, broken)
    for p in broken:
      outcomes[p] = "refreshed" if file_status(Path(checkout_dir) / p) == "ok" else "failed"
    still_broken = [p for p in broken if outcomes[p] == "failed"]
    if still_broken:
      raise ModelProvisioningError(f"model files still missing after git lfs pull: {still_broken}")

  if load_check:
    for p in rel_paths:
      name = Path(p).name
      if name not in DRIVING_PKLS or (name.startswith("big_") and not chestnut):
        continue
      result = try_load(checkout_dir, p)
      if result != "ok":
        outcomes[p] = f"load_{result}"

  Params().put("ModelStaticProvisioningStatus", json.dumps({"outcomes": outcomes, "ts": time.time()}))  # noqa: TID251 wall-clock timestamp
  return outcomes
