"""Run Sharp Cheddar twice on synthetic camera frames. Usage: python sharp_cheddar_replay.py MODEL.onnx"""
import hashlib
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort

MODEL_SHA256 = "350a47ea36e554fb71634c7361b2c2a2a3da07ecb211a4c6cff3d2c3013d1d82"
STATE_INPUTS = ("state_img_q", "state_desire_q", "state_feat_q")


def main(model_path):
  with Path(model_path).open("rb") as source:
    if hashlib.file_digest(source, "sha256").hexdigest() != MODEL_SHA256:
      raise ValueError("Expected the upstream Sharp Cheddar small model")

  options = ort.SessionOptions()
  options.intra_op_num_threads = 2
  session = ort.InferenceSession(str(model_path), options, providers=["CPUExecutionProvider"])
  dtypes = {"tensor(float)": np.float32, "tensor(float16)": np.float16, "tensor(uint8)": np.uint8,
            "tensor(int32)": np.int32, "tensor(int64)": np.int64, "tensor(bool)": np.bool_}
  inputs = {i.name: np.zeros(i.shape, dtype=dtypes[i.type]) for i in session.get_inputs()}
  names = ["outputs", *["next_" + key for key in STATE_INPUTS]]
  inputs["traffic_convention"][0, 0] = 1
  rng = np.random.default_rng(26)
  for frame in range(2):
    image = inputs["new_img"]
    image[:] = rng.integers(0, 256, size=image.shape, dtype=np.uint8)
    prediction, *state = session.run(names, inputs)
    if prediction.shape != (1, 2580) or not np.isfinite(prediction).all():
      raise ValueError(f"Invalid prediction at frame {frame}")
    for name, value in zip(STATE_INPUTS, state, strict=True):
      previous = inputs[name]
      if value.shape != previous.shape or value.dtype != previous.dtype or not np.isfinite(value).all():
        raise ValueError(f"Invalid {name} at frame {frame}")
      inputs[name] = value
    print(f"Frame {frame + 1}: {prediction.size} finite outputs and {len(state)} state buffers")


if __name__ == "__main__":
  main(sys.argv[1])
