from tests.conftest import auth_headers


def _setup(client, h):
    tid = client.post("/tenants", json={"name": "GP House", "type": "fund"}, headers=h).json()["id"]
    # portfolio company + an equity class to receive the SPV's holding
    portco = client.post(
        f"/tenants/{tid}/entities", json={"name": "Target Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    sc = client.post(
        f"/entities/{portco}/security-classes",
        json={"name": "Equity", "kind": "equity"},
        headers=h,
    ).json()["id"]
    # the SPV's own legal entity
    spv_entity = client.post(
        f"/tenants/{tid}/entities", json={"name": "Deal SPV I", "type": "spv"}, headers=h
    ).json()["id"]
    return tid, portco, sc, spv_entity


def test_spv_co_investors_and_summary(client):
    h = auth_headers(client)
    _, portco, _, spv_entity = _setup(client, h)
    sid = client.post(
        f"/entities/{spv_entity}/spv",
        json={"sponsor": "Angel Syndicate", "target_company": "Target Pvt Ltd", "portco_entity_id": portco},
        headers=h,
    ).json()["id"]

    c1 = client.post(
        f"/spvs/{sid}/co-investors", json={"name": "Angel A", "commitment": "2000000"}, headers=h
    ).json()["id"]
    client.post(
        f"/spvs/{sid}/co-investors", json={"name": "Angel B", "commitment": "3000000"}, headers=h
    )
    # one contributes
    paid = client.post(f"/spvs/{sid}/co-investors/{c1}/contribute", headers=h)
    assert paid.status_code == 200 and paid.json()["contributed"] == "2000000.00"

    s = client.get(f"/spvs/{sid}/summary", headers=h).json()
    assert s["co_investor_count"] == 2
    assert s["committed"] == "5000000.00"
    assert s["contributed"] == "2000000.00"


def test_spv_invest_sweeps_into_portco_cap_table(client):
    h = auth_headers(client)
    _, portco, sc, spv_entity = _setup(client, h)
    sid = client.post(
        f"/entities/{spv_entity}/spv",
        json={"sponsor": "Angel Syndicate", "target_company": "Target Pvt Ltd", "portco_entity_id": portco},
        headers=h,
    ).json()["id"]

    inv = client.post(
        f"/spvs/{sid}/invest",
        json={"security_class_id": sc, "quantity": 5000, "price_per_unit": "100"},
        headers=h,
    )
    assert inv.status_code == 201

    # the portco cap table now shows the SPV as a single combined holder
    ct = client.get(f"/entities/{portco}/cap-table", headers=h).json()
    assert ct["total_shares"] == 5000
    assert ct["holders"][0]["stakeholder_name"] == "SPV: Target Pvt Ltd"
    assert ct["holders"][0]["quantity"] == 5000


def test_spv_invest_requires_portco(client):
    h = auth_headers(client)
    tid = client.post("/tenants", json={"name": "T", "type": "fund"}, headers=h).json()["id"]
    spv_entity = client.post(
        f"/tenants/{tid}/entities", json={"name": "SPV", "type": "spv"}, headers=h
    ).json()["id"]
    sid = client.post(
        f"/entities/{spv_entity}/spv",
        json={"sponsor": "X", "target_company": "Y"},
        headers=h,
    ).json()["id"]
    r = client.post(
        f"/spvs/{sid}/invest",
        json={"security_class_id": "none", "quantity": 100, "price_per_unit": "1"},
        headers=h,
    )
    assert r.status_code == 400


def test_spv_access_control(client):
    owner = auth_headers(client, email="gp@spv.in")
    _, portco, _, spv_entity = _setup(client, owner)
    sid = client.post(
        f"/entities/{spv_entity}/spv",
        json={"sponsor": "X", "target_company": "Y", "portco_entity_id": portco},
        headers=owner,
    ).json()["id"]
    outsider = auth_headers(client, email="outsider@evil.in")
    assert client.get(f"/spvs/{sid}/co-investors", headers=outsider).status_code == 403
