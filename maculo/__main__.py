"""Run the server: python -m maculo"""

import logging
import os
import subprocess
import sys
from pathlib import Path

from .config import ROOT

log = logging.getLogger("maculo")


def _project_python() -> Path | None:
    exe = ROOT / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return exe if exe.exists() else None


def _relaunch_in_venv() -> None:
    """If started from the global Python, re-run inside the project's venv so the
    pinned packages are used. Set MACULO_NO_RELAUNCH=1 to skip this."""
    if sys.prefix != sys.base_prefix or os.environ.get("MACULO_NO_RELAUNCH"):
        return
    exe = _project_python()
    if exe is None:
        return
    print(f"Not in the project venv; restarting with {exe}", flush=True)
    try:
        code = subprocess.call(
            [str(exe), "-m", "maculo", *sys.argv[1:]],
            env={**os.environ, "MACULO_NO_RELAUNCH": "1"},
        )
    except KeyboardInterrupt:
        code = 0
    raise SystemExit(code)


def main() -> None:
    _relaunch_in_venv()

    import uvicorn

    from .config import get_settings

    s = get_settings()
    logging.basicConfig(
        level=s.log_level.upper(),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    if sys.prefix == sys.base_prefix:
        log.warning(
            "Running on the global Python (%s), not a virtual environment. If the "
            "models fail to load, create the venv described in README.md.",
            sys.executable,
        )
    uvicorn.run(
        "maculo.server:app",
        host=s.host,
        port=s.port,
        log_level=s.log_level,
        proxy_headers=s.trust_proxy,
        workers=1,  # each worker holds its own copy of the models
    )


if __name__ == "__main__":
    main()
