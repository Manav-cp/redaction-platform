import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("TABLE_NAME", "test-table")
os.environ.setdefault("RAW_BUCKET", "raw-bucket")
os.environ.setdefault("CLEAN_BUCKET", "clean-bucket")

sys.path.insert(0, str(ROOT / "processor"))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def api_module():
    return _load("api_handler", ROOT / "api" / "handler.py")


@pytest.fixture(scope="session")
def processor_module():
    return _load("processor_handler", ROOT / "processor" / "handler.py")
