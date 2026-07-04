import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_tmpdir = tempfile.mkdtemp(prefix="madplan-test-")
os.environ["DATABASE_PATH"] = os.path.join(_tmpdir, "madplan.db")
os.environ["LIFEHUB_API_TOKEN"] = "test-token"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

AUTH = {"Authorization": "Bearer test-token"}


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c
