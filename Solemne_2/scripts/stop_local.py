"""Detiene los procesos iniciados por run_local.py."""
import json
import os
import signal
from pathlib import Path

PIDS = Path(__file__).resolve().parent.parent / "runtime" / "pids.json"

if PIDS.exists():
    for name, pid in json.loads(PIDS.read_text()).items():
        try:
            os.killpg(pid, signal.SIGTERM) if hasattr(os, "killpg") else os.kill(pid, signal.SIGTERM)
            print(f"detenido {name}")
        except (ProcessLookupError, PermissionError):
            pass
    PIDS.unlink()
else:
    print("No hay procesos registrados")
