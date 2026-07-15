import os
import tempfile

# Point the app at an isolated temp SQLite DB BEFORE importing app modules.
_tmpdir = tempfile.mkdtemp(prefix="paper-test-")
os.environ["PAPER_DATABASE_URL"] = f"sqlite:///{_tmpdir}/test.db"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.ratelimit import funnel_limiter, login_limiter, signup_limiter  # noqa: E402


# Create the schema once; per-test isolation is achieved by wiping rows,
# which is far cheaper than drop_all/create_all on every test.
Base.metadata.create_all(engine)


@pytest.fixture()
def client():
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    # limiters are process-global in-memory state; isolate them per test too
    login_limiter._failures.clear()
    signup_limiter._failures.clear()
    funnel_limiter._failures.clear()
    with TestClient(app) as c:
        yield c


def auth_headers(client, email="founder@acme.in", password="s3cret-pass"):
    """Sign up (idempotent-ish) + log in, return Authorization header."""
    client.post(
        "/auth/signup",
        json={"email": email, "full_name": "Test Founder", "password": password},
    )
    token = client.post("/auth/login", json={"email": email, "password": password}).json()[
        "access_token"
    ]
    return {"Authorization": f"Bearer {token}"}
