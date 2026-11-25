"""Manager entry point for PitStop.

PitStop is optional and runs with restart_if_crash; if it can't start (for example aiohttp
isn't installed yet on a fresh install, or the port is taken) it must not crash-loop next to
the driving processes. Log the reason once and idle until the manager stops it."""
import time

from openpilot.common.swaglog import cloudlog


def main():
  try:
    from openpilot.pitstop.server import main as server_main
    server_main()
  except Exception:
    cloudlog.exception("pitstop: failed to start; idling (check /tmp/pitstop.log)")
  while True:
    time.sleep(60)


if __name__ == "__main__":
  main()
