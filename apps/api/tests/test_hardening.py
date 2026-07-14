from tests.conftest import auth_headers


def test_signup_rejects_short_password(client):
    r = client.post(
        "/auth/signup",
        json={"email": "short@x.in", "full_name": "S", "password": "short"},
    )
    assert r.status_code == 422


def test_login_rate_limited_after_failures(client):
    client.post(
        "/auth/signup",
        json={"email": "brute@x.in", "full_name": "B", "password": "correct-horse-1"},
    )
    # 5 failures fill the window...
    for _ in range(5):
        r = client.post("/auth/login", json={"email": "brute@x.in", "password": "wrong-pass"})
        assert r.status_code == 401
    # ...then even a correct login is blocked with 429
    blocked = client.post(
        "/auth/login", json={"email": "brute@x.in", "password": "correct-horse-1"}
    )
    assert blocked.status_code == 429


def test_successful_login_resets_limiter(client):
    client.post(
        "/auth/signup",
        json={"email": "resets@x.in", "full_name": "R", "password": "correct-horse-1"},
    )
    for _ in range(3):
        client.post("/auth/login", json={"email": "resets@x.in", "password": "nope-nope"})
    ok = client.post("/auth/login", json={"email": "resets@x.in", "password": "correct-horse-1"})
    assert ok.status_code == 200
    # counter reset: three more failures don't block
    for _ in range(3):
        client.post("/auth/login", json={"email": "resets@x.in", "password": "nope-nope"})
    ok2 = client.post("/auth/login", json={"email": "resets@x.in", "password": "correct-horse-1"})
    assert ok2.status_code == 200


def test_token_refresh(client):
    h = auth_headers(client, email="fresh@x.in")
    r = client.post("/auth/refresh", headers=h)
    assert r.status_code == 200
    new_token = r.json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {new_token}"})
    assert me.status_code == 200 and me.json()["email"] == "fresh@x.in"


def test_list_pagination(client):
    h = auth_headers(client)
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    for i in range(3):
        client.post(
            f"/entities/{eid}/documents",
            json={"template_key": "nda", "title": f"NDA {i}", "data": {"company": "Acme"}},
            headers=h,
        )
    assert len(client.get(f"/entities/{eid}/documents", headers=h).json()) == 3
    assert len(client.get(f"/entities/{eid}/documents?limit=2", headers=h).json()) == 2
    assert len(client.get(f"/entities/{eid}/documents?limit=2&offset=2", headers=h).json()) == 1
    # file cabinet honours the same params
    assert len(client.get(f"/entities/{eid}/files?limit=1", headers=h).json()) == 1
