"""Load only this project's optional runtime configuration; never print it."""
import os
from dotenv import dotenv_values
from .data import ROOT


def load_runtime_env():
    # Explicit path prevents searching parent/course directories. Shell wins.
    values = dotenv_values(ROOT / ".env", encoding="utf-8-sig", interpolate=False)
    # Models live in config.json (or explicit shell overrides), not the key file.
    for name in ("GROQ_API_KEY", "JINA_API_KEY"):
        if values.get(name) and not os.getenv(name):
            os.environ[name] = values[name]