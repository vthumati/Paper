from tests.conftest import auth_headers


def _setup(client, h):
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Equity", "kind": "equity"}, headers=h
    ).json()["id"]
    return eid, sc


# --- founder reverse-vesting ---
def test_founder_vesting_and_repurchase(client):
    h = auth_headers(client)
    eid, sc = _setup(client, h)
    founder = client.post(
        f"/entities/{eid}/stakeholders", json={"name": "Founder", "type": "founder"}, headers=h
    ).json()["id"]
    client.post(
        f"/entities/{eid}/issuances",
        json={"security_class_id": sc, "stakeholder_id": founder, "quantity": 4800000, "price_per_unit": "1", "issue_date": "2025-01-01"},
        headers=h,
    )
    fv = client.post(
        f"/entities/{eid}/founder-vesting",
        json={"stakeholder_id": founder, "security_class_id": sc, "total_shares": 4800000, "cliff_months": 12, "total_months": 48, "start_date": "2025-01-01"},
        headers=h,
    )
    assert fv.status_code == 201
    body = fv.json()
    # ~18 months in by 2026-mid -> 18/48 * 4.8M = 1.8M vested; 3.0M unvested
    assert body["vested"] > 0 and body["unvested"] > 0
    fid = body["id"]

    before = client.get(f"/entities/{eid}/cap-table", headers=h).json()["total_shares"]
    r = client.post(f"/founder-vesting/{fid}/repurchase-unvested", headers=h).json()
    assert r["repurchased_shares"] == body["unvested"]
    after = client.get(f"/entities/{eid}/cap-table", headers=h).json()["total_shares"]
    assert after == before - body["unvested"]


# --- cashless ESOP exercise ---
def test_cashless_exercise_nets_shares(client):
    h = auth_headers(client)
    eid, sc = _setup(client, h)
    emp = client.post(
        f"/entities/{eid}/stakeholders", json={"name": "Emp", "type": "employee"}, headers=h
    ).json()["id"]
    scheme = client.post(
        f"/entities/{eid}/esop/schemes", json={"name": "ESOP", "pool_size": 100000}, headers=h
    ).json()["id"]
    gid = client.post(
        f"/entities/{eid}/esop/grants",
        json={"scheme_id": scheme, "stakeholder_id": emp, "quantity": 4800, "exercise_price": "10", "grant_date": "2025-01-01"},
        headers=h,
    ).json()["id"]
    # cashless exercise of 1000 options, FMV 100, strike 10 -> net = 1000*(90/100)=900
    ex = client.post(
        f"/esop/grants/{gid}/exercise?as_of=2026-01-01",
        json={"quantity": 1000, "security_class_id": sc, "fmv_per_share": "100", "cashless": True},
        headers=h,
    ).json()
    assert ex["cashless"] is True and ex["net_shares"] == 900
    assert ex["quantity"] == 1000  # gross consumed
    # 1000 gross consumed from grant
    g = client.get(f"/esop/grants/{gid}?as_of=2026-01-01", headers=h).json()
    assert g["exercised"] == 1000
    # only 900 net shares hit the cap table
    ct = client.get(f"/entities/{eid}/cap-table", headers=h).json()
    assert ct["total_shares"] == 900


# --- data room Q&A + expiry + watermark ---
def test_dataroom_qa_and_watermark(client):
    h = auth_headers(client)
    eid, sc = _setup(client, h)
    did = client.post(
        f"/entities/{eid}/documents", json={"template_key": "sha", "data": {"company": "Acme"}}, headers=h
    ).json()["id"]
    rid = client.post(f"/entities/{eid}/data-rooms", json={"name": "DR"}, headers=h).json()["id"]
    item = client.post(f"/data-rooms/{rid}/items", json={"document_id": did}, headers=h).json()["items"][0]["id"]

    # watermark on view
    v = client.post(f"/data-rooms/{rid}/items/{item}/view", headers=h).json()
    assert v["content"].startswith("CONFIDENTIAL")

    # Q&A
    q = client.post(f"/data-rooms/{rid}/questions", json={"question": "What is the runway?"}, headers=h)
    assert q.status_code == 201 and q.json()["answer"] is None
    qid = q.json()["id"]
    a = client.post(f"/data-room-questions/{qid}/answer", json={"answer": "18 months."}, headers=h)
    assert a.status_code == 200 and a.json()["answer"] == "18 months."


def test_expired_grant_hidden_from_portal(client):
    owner = auth_headers(client, email="owner@acme.in")
    eid, sc = _setup(client, owner)
    did = client.post(
        f"/entities/{eid}/documents", json={"template_key": "sha", "data": {"company": "Acme"}}, headers=owner
    ).json()["id"]
    rid = client.post(f"/entities/{eid}/data-rooms", json={"name": "DR"}, headers=owner).json()["id"]
    client.post(f"/data-rooms/{rid}/items", json={"document_id": did}, headers=owner)
    # expired grant
    client.post(
        f"/data-rooms/{rid}/grants",
        json={"email": "inv@x.in", "expiry": "2020-01-01"},
        headers=owner,
    )
    client.post(f"/entities/{eid}/investor-access", json={"email": "inv@x.in"}, headers=owner)

    inv = auth_headers(client, email="inv@x.in")
    entry = client.get("/portal", headers=inv).json()["companies"][0]
    assert entry["documents"] == []  # expired -> not shared
