from tests.conftest import auth_headers


def _entity(client, h):
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=h).json()["id"]
    return client.post(
        f"/tenants/{tid}/entities", json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]


def test_periodic_generation_gst_and_tds(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    obs = client.post(
        f"/entities/{eid}/compliance/generate-periodic",
        json={"financial_year_end": "2026-03-31"},
        headers=h,
    ).json()
    codes = [o["form_code"] for o in obs]
    assert codes.count("GSTR-3B") == 12  # monthly
    assert codes.count("TDS 26Q") == 4  # quarterly
    # idempotent
    obs2 = client.post(
        f"/entities/{eid}/compliance/generate-periodic",
        json={"financial_year_end": "2026-03-31"},
        headers=h,
    ).json()
    assert [o["form_code"] for o in obs2].count("GSTR-3B") == 12


def test_health_score(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    obs = client.post(
        f"/entities/{eid}/compliance/generate",
        json={"financial_year_end": "2026-03-31"},
        headers=h,
    ).json()
    health = client.get(f"/entities/{eid}/compliance/health", headers=h).json()
    assert health["total"] == 5 and health["filed"] == 0 and health["score"] == 0
    # file one -> score moves
    client.post(f"/compliance/{obs[0]['id']}/status", json={"status": "filed"}, headers=h)
    health2 = client.get(f"/entities/{eid}/compliance/health", headers=h).json()
    assert health2["filed"] == 1 and health2["score"] == 20  # 1/5


def test_round_close_creates_pas3(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Eq", "kind": "ccps"}, headers=h
    ).json()["id"]
    rid = client.post(
        f"/entities/{eid}/rounds",
        json={"name": "Seed", "price_per_share": "100", "security_class_id": sc},
        headers=h,
    ).json()["id"]
    c = client.post(
        f"/rounds/{rid}/commitments",
        json={"investor_name": "Angel", "amount": "1000000"},
        headers=h,
    ).json()["id"]
    client.post(f"/rounds/{rid}/commitments/{c}/status", json={"status": "funded"}, headers=h)
    client.post(f"/rounds/{rid}/close", headers=h)

    obs = client.get(f"/entities/{eid}/compliance", headers=h).json()
    assert any(o["form_code"] == "PAS-3" for o in obs)


def test_special_resolution_creates_mgt14(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    rid = client.post(
        f"/entities/{eid}/resolutions",
        json={"type": "special", "title": "Amend AoA", "text": "RESOLVED..."},
        headers=h,
    ).json()["id"]
    client.post(f"/resolutions/{rid}/status", json={"status": "passed"}, headers=h)
    obs = client.get(f"/entities/{eid}/compliance", headers=h).json()
    assert any(o["form_code"] == "MGT-14" for o in obs)


def test_director_change_creates_dir12(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    client.post(
        f"/entities/{eid}/directors",
        json={"name": "A. Rao", "designation": "director", "appointed_on": "2026-01-01"},
        headers=h,
    )
    obs = client.get(f"/entities/{eid}/compliance", headers=h).json()
    assert any(o["form_code"] == "DIR-12" for o in obs)
