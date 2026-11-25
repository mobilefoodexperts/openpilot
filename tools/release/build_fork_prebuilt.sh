#!/usr/bin/env bash
# Build a "-prebuilt" branch of this fork ON A COMMA DEVICE.
#
# Same steps as tools/release/build_release.sh (sunnypilot's own release build), minus
# the parts only sunnypilot's CI rigs can do: no release-signed panda firmware (no cert
# on a user device), no test_onroad, and no push from the device. The tinygrad models
# have to be compiled on the device's own Adreno GPU, which is why this can't run on a
# GitHub runner.
#
# Usage, over SSH on the comma (openpilot stopped):
#   git clone --recurse-submodules -b sunnypilot-nov-2026 https://github.com/mobilefoodexperts/openpilot.git /data/src_openpilot
#   cd /data/src_openpilot && git lfs pull && git submodule foreach git lfs pull
#   PREBUILT_BRANCH=sunnypilot-nov-2026-prebuilt tools/release/build_fork_prebuilt.sh
# Then from a PC: git fetch ssh://comma@<ip>/data/src_openpilot <branch>, push it to GitHub,
# and reinstall the comma from `mobilefoodexperts/<branch>` so /data/openpilot is a normal
# clone again (this script leaves it as a worktree of /data/src_openpilot, which the
# updater doesn't expect). See docs/TESLA_HW1_FORK_BUILD.md.
set -e
set -x

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null && pwd)"
cd "$DIR"

BUILD_DIR=/data/openpilot
SOURCE_DIR="$(git rev-parse --show-toplevel)"
BUILD_BRANCH="${PREBUILT_BRANCH:?set PREBUILT_BRANCH, e.g. sunnypilot-nov-2026-prebuilt}"

if [ "$(realpath "$SOURCE_DIR")" = "$(realpath "$BUILD_DIR" 2>/dev/null || echo none)" ]; then
  echo "Run this from a separate source clone (e.g. /data/src_openpilot), not from $BUILD_DIR"
  exit 1
fi
if [ ! -f /AGNOS ]; then
  echo "This must run on a comma device (models are compiled for its GPU)"
  exit 1
fi

export PYTHONPATH="$BUILD_DIR:$BUILD_DIR/msgq_repo:$BUILD_DIR/opendbc_repo:$BUILD_DIR/rednose_repo:$BUILD_DIR/teleoprtc_repo:$BUILD_DIR/tinygrad_repo"

source "$DIR/identity.sh"

echo "[-] Setting up repo T=$SECONDS"
if ! git -C "$SOURCE_DIR" worktree remove --force "$BUILD_DIR" 2>/dev/null; then
  rm -rf "$BUILD_DIR"
fi
git -C "$SOURCE_DIR" worktree prune
git -C "$SOURCE_DIR" worktree add --detach --no-checkout "$BUILD_DIR"
cd "$BUILD_DIR"
git update-ref -d "refs/heads/$BUILD_BRANCH" || true
git symbolic-ref HEAD "refs/heads/$BUILD_BRANCH"
git read-tree --empty

echo "[-] copying files T=$SECONDS"
cd "$SOURCE_DIR"
./tools/release/release_files.py | xargs -0 cp -pR --parents -t "$BUILD_DIR" --

cd "$BUILD_DIR"
source "$SOURCE_DIR/tools/release/setup_lfs.sh"

for policy in /sys/devices/system/cpu/cpufreq/policy*; do
  [ -d "$policy" ] || continue
  hardware_max="$(cat "$policy/cpuinfo_max_freq")"
  echo "$hardware_max" | sudo tee "$policy/scaling_max_freq" >/dev/null
done

scons
scons panda/

if test "$(git submodule--helper list | wc -l)" -gt "0"; then
  echo "submodules found:"
  git submodule--helper list
  exit 1
fi

# Cleanup (same as build_release.sh)
find . -name '*.a' -delete
find . -name '*.o' -delete
find . -name '*.os' -delete
find . -name '*.pyc' -delete
find . -name '__pycache__' -delete
rm -rf .sconsign.dblite Jenkinsfile tools/release/
rm -f openpilot/selfdrive/modeld/models/*.onnx*
rm -f openpilot/sunnypilot/modeld*/models/*.onnx*
find openpilot/third_party/ -name '*x86*' -exec rm -r {} +
find openpilot/third_party/ -name '*Darwin*' -exec rm -r {} +
git checkout openpilot/third_party/ 2>/dev/null || true

touch prebuilt

VERSION=$(cat openpilot/sunnypilot/common/version.h | awk -F[\"-]  '{print $2}')
git -c core.compression=0 add -f .
git -c core.compression=0 -c gc.auto=0 commit -m "sunnypilot Tesla HW1 v$VERSION prebuilt (from $(git -C "$SOURCE_DIR" rev-parse --short HEAD))"
source "$SOURCE_DIR/tools/release/check_file_sizes.sh"

echo "[-] done T=$SECONDS: branch $BUILD_BRANCH is ready in $BUILD_DIR; fetch it from /data/src_openpilot"
