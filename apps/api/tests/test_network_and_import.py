from app.clock import today_ist
from tests.conftest import auth_headers


def _fund(client, h):
    tid = client.post("/tenants", json={"name": "GP House", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Alpha Fund I", "type": "fund"}, headers=h
    ).json()["id"]
    return client.post(f"/entities/{eid}/fund", json={"sebi_category": "II"}, headers=h).json()["id"]


def test_network_dedupes_and_ranks(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    today = today_ist().isoformat()

    # the same person (by email) is a contact on a deal AND an LP prospect
    d1 = client.post(f"/funds/{fid}/deals", json={"company_name": "Acme"}, headers=h).json()["id"]
    cid = client.post(f"/deals/{d1}/contacts",
                      json={"name": "Asha Rao", "role": "Founder", "email": "asha@x.in"},
                      headers=h).json()["contacts"][0]["id"]
    client.post(f"/deals/{d1}/activities", headers=h,
                json={"kind": "meeting", "body": "Pitch", "occurred_on": today, "contact_id": cid})
    client.post(f"/funds/{fid}/prospects",
                json={"name": "Asha Rao", "email": "asha@x.in", "target_commitment": "10000000"},
                headers=h)
    # a second, untouched person
    client.post(f"/deals/{d1}/contacts", json={"name": "Vikram Shah"}, headers=h)

    net = client.get(f"/funds/{fid}/network", headers=h).json()
    assert net["count"] == 2
    asha = net["people"][0]  # strongest first
    assert asha["name"] == "Asha Rao"
    assert sorted(asha["links"]) == ["LP fundraise", "deal: Acme"]
    assert asha["strength"] == 55            # 1 attributed touch today
    assert asha["last_touch"] == today
    assert net["people"][1] == {
        "name": "Vikram Shah", "role": None, "email": None,
        "links": ["deal: Acme"], "strength": 0, "last_touch": None,
    }


def test_deals_csv_import_validate_then_apply(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    good = (
        "company_name,sector,stage,amount,source\n"
        "Acme Robotics,DeepTech,screening,15000000,IIT network\n"
        "BlueLeaf Foods,,sourced,,\n"
    )
    r = client.post(f"/funds/{fid}/deals/import", json={"csv": good}, headers=h).json()
    assert r == {"valid": True, "rows": 2, "errors": []}
    # dry run creates nothing
    assert client.get(f"/funds/{fid}/deals", headers=h).json() == []

    r = client.post(f"/funds/{fid}/deals/import", json={"csv": good, "apply": True}, headers=h).json()
    assert r["applied"] is True and r["imported"] == 2
    deals = client.get(f"/funds/{fid}/deals", headers=h).json()
    by = {d["company_name"]: d for d in deals}
    assert by["Acme Robotics"]["stage"] == "screening"
    assert by["Acme Robotics"]["source"] == "IIT network"
    assert by["BlueLeaf Foods"]["stage"] == "sourced" and by["BlueLeaf Foods"]["amount"] == "0.00"


def test_deals_csv_import_rejects_bad_rows(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    bad = (
        "company_name,stage,amount\n"
        ",sourced,100\n"
        "Acme,warp_speed,100\n"
        "Beta,sourced,not-a-number\n"
    )
    r = client.post(f"/funds/{fid}/deals/import", json={"csv": bad}, headers=h).json()
    assert r["valid"] is False and len(r["errors"]) == 3
    # applying an invalid CSV is refused outright
    assert client.post(f"/funds/{fid}/deals/import", json={"csv": bad, "apply": True}, headers=h).status_code == 400
    # missing the required column
    assert client.post(f"/funds/{fid}/deals/import", json={"csv": "name\nx\n"}, headers=h).status_code == 400
