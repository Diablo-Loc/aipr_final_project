"""Windows-compatible entry point. Never reads .env or prints credentials."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
PYTHON = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def setup():
    if sys.version_info[:2] != (3, 11):
        raise SystemExit("Use Python 3.11: py -3.11 run.py setup (locked environment)")
    env = os.environ.copy()
    env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    if not PYTHON.exists():
        subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True, env=env)
    check_python()
    lock = ROOT / "requirements.lock.txt"
    subprocess.run([str(PYTHON), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(lock if lock.exists() else ROOT / "requirements.txt")], check=True, env=env)


def check_python():
    result = subprocess.run([str(PYTHON), "-c", "import sys; sys.exit(sys.version_info[:2] != (3, 11))"])
    if result.returncode:
        raise SystemExit("Existing .venv must use Python 3.11; create a Python 3.11 environment")


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "demo"
    if command == "setup":
        setup()
        return
    if not PYTHON.exists():
        setup()
    check_python()
    commands = {"demo": ["-m", "src.cli"], "eval": ["scripts/eval.py"], "test": ["-m", "unittest", "discover", "-s", "tests", "-v"], "interop": ["scripts/second_client.py"], "audit": ["scripts/check_compliance.py"], "report": ["scripts/build_report.py"], "preflight": ["scripts/preflight.py"]}
    if command not in commands:
        raise SystemExit("Commands: setup, demo, eval, test, interop, audit, report")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    raise SystemExit(subprocess.run([str(PYTHON), *commands[command], *sys.argv[2:]], cwd=ROOT, env=env).returncode)


if __name__ == "__main__":
    main()
