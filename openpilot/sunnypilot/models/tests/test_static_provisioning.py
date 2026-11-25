import json
from unittest.mock import patch

import pytest

from openpilot.sunnypilot.models import static_provisioning as sp

BIG = "openpilot/selfdrive/modeld/models/big_driving_tinygrad.pkl"
WARP = "openpilot/sunnypilot/modeld_v2/models/driving_warp_1344x760_tinygrad.pkl"
POINTER = b"version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 123\n"


def _write(root, rel, data):
  path = root / rel
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_bytes(data)


class _FakeParams:
  store: dict = {}

  def put(self, key, value):
    _FakeParams.store[key] = value


@pytest.fixture
def checkout(tmp_path):
  _FakeParams.store = {}
  with patch.object(sp, "_tracked_model_files", return_value=[BIG, WARP]), patch.object(sp, "Params", _FakeParams):
    yield tmp_path


def test_file_status(tmp_path):
  _write(tmp_path, "a.pkl", b"\x80\x04real pickle")
  _write(tmp_path, "b.pkl", POINTER)
  _write(tmp_path, "c.pkl", b"")
  assert sp.file_status(tmp_path / "a.pkl") == "ok"
  assert sp.file_status(tmp_path / "b.pkl") == "lfs_pointer"
  assert sp.file_status(tmp_path / "c.pkl") == "missing"
  assert sp.file_status(tmp_path / "nope.pkl") == "missing"


def test_all_ok_no_pull_and_status_written(checkout):
  _write(checkout, BIG, b"weights")
  _write(checkout, WARP, b"weights")
  with patch.object(sp, "_lfs_pull") as pull:
    outcomes = sp.verify_and_refresh_static_models(str(checkout), chestnut=False, load_check=False)
  pull.assert_not_called()
  assert outcomes == {BIG: "ok", WARP: "ok"}
  assert json.loads(_FakeParams.store["ModelStaticProvisioningStatus"])["outcomes"] == outcomes


def test_pointer_is_pulled_and_refreshed(checkout):
  _write(checkout, BIG, b"weights")
  _write(checkout, WARP, POINTER)
  with patch.object(sp, "_lfs_pull", side_effect=lambda d, paths: _write(checkout, WARP, b"weights")) as pull:
    outcomes = sp.verify_and_refresh_static_models(str(checkout), load_check=False)
  pull.assert_called_once_with(str(checkout), [WARP])
  assert outcomes[WARP] == "refreshed"


def test_pointer_that_stays_broken_fails_update(checkout):
  _write(checkout, BIG, b"weights")
  _write(checkout, WARP, POINTER)
  with patch.object(sp, "_lfs_pull"), pytest.raises(sp.ModelProvisioningError):
    sp.verify_and_refresh_static_models(str(checkout), load_check=False)
  assert "ModelStaticProvisioningStatus" not in _FakeParams.store


def test_big_model_load_only_with_chestnut_and_never_fatal(checkout):
  _write(checkout, BIG, b"weights")
  _write(checkout, WARP, b"weights")
  with patch.object(sp, "try_load", return_value="failed") as load:
    outcomes = sp.verify_and_refresh_static_models(str(checkout), chestnut=False)
    load.assert_not_called()
    outcomes = sp.verify_and_refresh_static_models(str(checkout), chestnut=True)
    load.assert_called_once_with(str(checkout), BIG)
  assert outcomes[BIG] == "load_failed"
