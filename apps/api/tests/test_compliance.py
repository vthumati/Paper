from tests.conftest import auth_headers


def _entity(client, h):
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=h).json()["id"]
    return client.post(
        f"/tenants/{tid}/entities", json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]


def test_generate_calendar_is_idempotent(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    r = client.post(
        f"/entities/{eid}/compliance/generate",
        json={"financial_year_end": "2026-03-31"},
        headers=h,
    )
    assert r.status_code == 200
    obs = r.json()
    codes = {o["form_code"] for o in obs}
    assert {"AOC-4", "MGT-7", "DIR-3 KYC", "DPT-3", "ADT-1"} <= codes
    n = len(obs)
    # regenerate for same FY -> no duplicates
    r2 = client.post(
        f"/entities/{eid}/compliance/generate",
        json={"financial_year_end": "2026-03-31"},
        headers=h,
    )
    assert len(r2.json()) == n


def test_overdue_flag_respects_as_of(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    client.post(
        f"/entities/{eid}/compliance/generate",
        json={"financial_year_end": "2026-03-31"},
        headers=h,
    )
    # AOC-4 is due 2026-10-30; as_of after that -> overdue
    obs = client.get(f"/entities/{eid}/compliance?as_of=2026-12-01", headers=h).json()
    aoc4 = next(o for o in obs if o["form_code"] == "AOC-4")
    assert aoc4["overdue"] is True
    # as_of before due date -> not overdue
    obs_early = client.get(f"/entities/{eid}/compliance?as_of=2026-06-01", headers=h).json()
    aoc4_early = next(o for o in obs_early if o["form_code"] == "AOC-4")
    assert aoc4_early["overdue"] is False


def test_status_update_clears_overdue(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    obs = client.post(
        f"/entities/{eid}/compliance/generate",
        json={"financial_year_end": "2026-03-31"},
        headers=h,
    ).json()
    aoc4_id = next(o["id"] for o in obs if o["form_code"] == "AOC-4")
    r = client.post(
        f"/compliance/{aoc4_id}/status",
        json={"status": "filed", "srn": "SRN123456"},
        headers=h,
    )
    assert r.status_code == 200 and r.json()["status"] == "filed" and r.json()["srn"] == "SRN123456"
    # filed obligations are never overdue
    obs2 = client.get(f"/entities/{eid}/compliance?as_of=2027-01-01", headers=h).json()
    aoc4 = next(o for o in obs2 if o["form_code"] == "AOC-4")
    assert aoc4["overdue"] is False


def test_compliance_access_control(client):
    owner = auth_headers(client, email="owner@acme.in")
    eid = _entity(client, owner)
    outsider = auth_headers(client, email="outsider@evil.in")
    assert (
        client.post(
            f"/entities/{eid}/compliance/generate",
            json={"financial_year_end": "2026-03-31"},
            headers=outsider,
        ).status_code
        == 403
    )
