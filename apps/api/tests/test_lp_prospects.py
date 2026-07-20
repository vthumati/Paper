from tests.conftest import auth_headers


def _fund(client, h, corpus="500000000"):
    tid = client.post("/tenants", json={"name": "GP House", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Alpha Fund I", "type": "fund"}, headers=h
    ).json()["id"]
    fid = client.post(
        f"/entities/{eid}/fund", json={"sebi_category": "II", "target_corpus": corpus}, headers=h
    ).json()["id"]
    return fid


def test_prospect_pipeline_and_summary(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    client.post(f"/funds/{fid}/prospects", headers=h,
                json={"name": "SIDBI", "firm": "SIDBI", "kind": "institutional", "target_commitment": "150000000"})
    s = client.post(f"/funds/{fid}/prospects", headers=h,
                    json={"name": "Family Office X", "kind": "family_office", "target_commitment": "80000000"}).json()
    assert len(s["prospects"]) == 2
    sidbi = next(p for p in s["prospects"] if p["name"] == "SIDBI")

    # move SIDBI to soft-circled
    s = client.post(f"/funds/{fid}/prospects/{sidbi['id']}/stage", headers=h,
                    json={"stage": "soft_circled"}).json()
    assert s["soft_circled"] == "150000000.00"
    assert s["pipeline"] == "230000000.00"       # both still active
    assert s["committed"] == "0.00"
    assert s["target_corpus"] == "500000000.00"


def test_convert_prospect_creates_lp(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    s = client.post(f"/funds/{fid}/prospects", headers=h,
                    json={"name": "Angel Group", "kind": "hni", "target_commitment": "40000000"}).json()
    pid = s["prospects"][0]["id"]

    lp = client.post(f"/funds/{fid}/prospects/{pid}/convert", json={}, headers=h)
    assert lp.status_code == 201
    assert lp.json()["commitment"] == "40000000.00"

    # prospect now shows committed + linked; an LP exists; fundraise reflects it
    s2 = client.get(f"/funds/{fid}/fundraise", headers=h).json()
    p = s2["prospects"][0]
    assert p["stage"] == "committed" and p["lp_id"] is not None
    assert s2["committed"] == "40000000.00"
    assert s2["progress_pct"] == 8.0             # 40m / 500m
    assert len(client.get(f"/funds/{fid}/lps", headers=h).json()) == 1

    # double convert is guarded
    dup = client.post(f"/funds/{fid}/prospects/{pid}/convert", json={}, headers=h)
    assert dup.status_code == 409


def test_convert_with_explicit_commitment_and_scope(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    s = client.post(f"/funds/{fid}/prospects", headers=h,
                    json={"name": "LP", "target_commitment": "10000000"}).json()
    pid = s["prospects"][0]["id"]
    # override the commitment at conversion
    lp = client.post(f"/funds/{fid}/prospects/{pid}/convert", json={"commitment": "25000000"}, headers=h)
    assert lp.json()["commitment"] == "25000000.00"
    # unknown prospect -> 404
    assert client.post(f"/funds/{fid}/prospects/nope/convert", json={}, headers=h).status_code == 404
