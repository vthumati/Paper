from tests.conftest import auth_headers


def _fund(client, h):
    tid = client.post("/tenants", json={"name": "GP House", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Alpha Fund I", "type": "fund"}, headers=h
    ).json()["id"]
    fid = client.post(f"/entities/{eid}/fund", json={"sebi_category": "II"}, headers=h).json()["id"]
    return fid


def _investment(client, h, fid, name="Acme", amount="10000000"):
    return client.post(
        f"/funds/{fid}/portfolio", json={"company_name": name, "amount": amount}, headers=h
    ).json()["id"]


def test_policy_and_valuation_updates_mark(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    iid = _investment(client, h, fid)
    client.put(
        f"/funds/{fid}/valuation-policy",
        json={"valuer_name": "Kroll India", "valuation_frequency_months": 6},
        headers=h,
    )
    r = client.post(
        f"/funds/{fid}/portfolio/{iid}/valuations",
        json={"as_of": "2026-07-01", "value": "18000000", "methodology": "ipev_market",
              "valuer": "Kroll India", "is_independent": True},
        headers=h,
    )
    assert r.status_code == 201
    # the valuation rolls into the holding's mark
    pf = client.get(f"/funds/{fid}/portfolio", headers=h).json()
    assert pf[0]["current_value"] == "18000000.00"

    s = client.get(f"/funds/{fid}/valuations", headers=h).json()
    assert s["policy"]["valuer_name"] == "Kroll India"
    assert s["totals"] == {"holdings": 1, "valued": 1, "stale": 0, "independent": 1}
    assert s["holdings"][0]["latest"]["methodology_label"].startswith("IPEV")


def test_latest_valuation_wins_and_staleness(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    client.put(f"/funds/{fid}/valuation-policy", json={"valuation_frequency_months": 6}, headers=h)
    acme = _investment(client, h, fid, "Acme")
    beta = _investment(client, h, fid, "Beta", "5000000")

    # Acme: an old then a recent valuation -> latest (recent) wins, not stale
    client.post(f"/funds/{fid}/portfolio/{acme}/valuations", headers=h,
                json={"as_of": "2025-01-01", "value": "12000000", "methodology": "cost"})
    client.post(f"/funds/{fid}/portfolio/{acme}/valuations", headers=h,
                json={"as_of": "2026-07-01", "value": "20000000", "methodology": "ipev_market",
                      "valuer": "Kroll", "is_independent": True})
    # Beta: only an old valuation -> stale
    client.post(f"/funds/{fid}/portfolio/{beta}/valuations", headers=h,
                json={"as_of": "2025-01-01", "value": "4000000", "methodology": "cost",
                      "is_independent": False})

    s = client.get(f"/funds/{fid}/valuations", headers=h).json()
    by = {h2["company_name"]: h2 for h2 in s["holdings"]}
    assert by["Acme"]["latest"]["value"] == "20000000.00"   # latest by as_of
    assert by["Acme"]["valuations"] == 2
    assert by["Acme"]["stale"] is False
    assert by["Beta"]["stale"] is True
    assert s["totals"]["stale"] == 1
    assert s["totals"]["independent"] == 1                    # only Acme's latest is independent


def test_valuation_report_document(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    iid = _investment(client, h, fid)
    client.post(f"/funds/{fid}/portfolio/{iid}/valuations", headers=h,
                json={"as_of": "2026-07-01", "value": "11000000", "methodology": "dcf"})
    r = client.post(f"/funds/{fid}/valuations/report", headers=h)
    assert r.status_code == 201
    assert r.json()["subject_type"] == "fund_valuation"
