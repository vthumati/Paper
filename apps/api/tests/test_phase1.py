from tests.conftest import auth_headers


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_signup_login_me(client):
    r = client.post(
        "/auth/signup",
        json={"email": "a@x.in", "full_name": "Ann", "password": "pw12345678"},
    )
    assert r.status_code == 201
    # duplicate email rejected
    assert client.post(
        "/auth/signup",
        json={"email": "a@x.in", "full_name": "Ann", "password": "pw12345678"},
    ).status_code == 409
    # bad password
    assert client.post(
        "/auth/login", json={"email": "a@x.in", "password": "wrong"}
    ).status_code == 401
    token = client.post(
        "/auth/login", json={"email": "a@x.in", "password": "pw12345678"}
    ).json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200 and me.json()["email"] == "a@x.in"


def test_me_requires_token(client):
    assert client.get("/auth/me").status_code in (401, 403)


def test_tenant_and_entity_flow(client):
    h = auth_headers(client)
    t = client.post("/tenants", json={"name": "Acme Labs", "type": "company"}, headers=h)
    assert t.status_code == 201
    tid = t.json()["id"]
    assert len(client.get("/tenants", headers=h).json()) == 1

    e = client.post(
        f"/tenants/{tid}/entities",
        json={"name": "Acme Labs Pvt Ltd", "type": "pvt_ltd"},
        headers=h,
    )
    assert e.status_code == 201
    eid = e.json()["id"]
    assert client.get(f"/entities/{eid}", headers=h).json()["name"] == "Acme Labs Pvt Ltd"


def test_tenant_isolation(client):
    owner = auth_headers(client, email="owner@acme.in")
    tid = client.post(
        "/tenants", json={"name": "Acme", "type": "company"}, headers=owner
    ).json()["id"]

    outsider = auth_headers(client, email="outsider@evil.in")
    # outsider is not a member -> 403
    assert client.get(f"/tenants/{tid}", headers=outsider).status_code == 403
    assert (
        client.post(
            f"/tenants/{tid}/entities",
            json={"name": "X", "type": "pvt_ltd"},
            headers=outsider,
        ).status_code
        == 403
    )


def test_cap_table_projection(client):
    h = auth_headers(client)
    tid = client.post(
        "/tenants", json={"name": "Acme", "type": "company"}, headers=h
    ).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities",
        json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"},
        headers=h,
    ).json()["id"]

    sc = client.post(
        f"/entities/{eid}/security-classes",
        json={"name": "Equity", "kind": "equity", "par_value": "10"},
        headers=h,
    ).json()["id"]
    f1 = client.post(
        f"/entities/{eid}/stakeholders",
        json={"name": "Founder A", "type": "founder"},
        headers=h,
    ).json()["id"]
    inv = client.post(
        f"/entities/{eid}/stakeholders",
        json={"name": "Seed Fund", "type": "investor"},
        headers=h,
    ).json()["id"]

    # Founder gets 8000 shares @ par 10; investor gets 2000 @ 100
    client.post(
        f"/entities/{eid}/issuances",
        json={
            "security_class_id": sc,
            "stakeholder_id": f1,
            "quantity": 8000,
            "price_per_unit": "10",
            "issue_date": "2026-01-01",
        },
        headers=h,
    )
    client.post(
        f"/entities/{eid}/issuances",
        json={
            "security_class_id": sc,
            "stakeholder_id": inv,
            "quantity": 2000,
            "price_per_unit": "100",
            "issue_date": "2026-02-01",
        },
        headers=h,
    )

    ct = client.get(f"/entities/{eid}/cap-table", headers=h).json()
    assert ct["total_shares"] == 10000
    # 8000*10 + 2000*100 = 80000 + 200000 = 280000 (money to paise)
    assert ct["total_invested"] == "280000.00"
    by_holder = {r["stakeholder_name"]: r for r in ct["holders"]}
    assert by_holder["Founder A"]["ownership_pct"] == 80.0
    assert by_holder["Seed Fund"]["ownership_pct"] == 20.0


def test_issuance_validates_entity_scope(client):
    h = auth_headers(client)
    tid = client.post(
        "/tenants", json={"name": "Acme", "type": "company"}, headers=h
    ).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities",
        json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"},
        headers=h,
    ).json()["id"]
    # unknown security class / stakeholder ids -> 400
    bad = client.post(
        f"/entities/{eid}/issuances",
        json={
            "security_class_id": "nope",
            "stakeholder_id": "nope",
            "quantity": 100,
            "price_per_unit": "1",
            "issue_date": "2026-01-01",
        },
        headers=h,
    )
    assert bad.status_code == 400
