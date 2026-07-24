import datetime as dt

from app.clock import today_ist
from tests.conftest import auth_headers


def test_signup_rate_limited_per_ip(client):
    for i in range(20):
        client.post(
            "/auth/signup",
            json={"email": f"user{i}@spam.in", "full_name": "X", "password": "pw12345678"},
        )
    r = client.post(
        "/auth/signup",
        json={"email": "one-more@spam.in", "full_name": "X", "password": "pw12345678"},
    )
    assert r.status_code == 429


def test_numeric_bounds_rejected(client):
    h = auth_headers(client)
    tid = client.post("/tenants", json={"name": "B", "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "B Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]

    # negative SAFE principal / discount >= 1
    assert client.post(
        f"/entities/{eid}/instruments",
        json={"investor_name": "X", "instrument_type": "safe", "principal": "-5",
              "issue_date": "2026-01-01"},
        headers=h,
    ).status_code == 422
    assert client.post(
        f"/entities/{eid}/instruments",
        json={"investor_name": "X", "instrument_type": "safe", "principal": "100",
              "discount_pct": "1.5", "issue_date": "2026-01-01"},
        headers=h,
    ).status_code == 422

    # fund carry must be < 1 (the catch-up formula divides by 1 - carry)
    ftid = client.post("/tenants", json={"name": "G", "type": "fund"}, headers=h).json()["id"]
    feid = client.post(
        f"/tenants/{ftid}/entities", json={"name": "G Fund", "type": "fund"}, headers=h
    ).json()["id"]
    assert client.post(
        f"/entities/{feid}/fund", json={"sebi_category": "II", "carry_pct": "1.5"}, headers=h
    ).status_code == 422
    assert client.post(
        f"/entities/{feid}/fund", json={"sebi_category": "II", "hurdle_pct": "-0.1"}, headers=h
    ).status_code == 422

    # negative-priced secondary sale request
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Eq", "kind": "equity"}, headers=h
    ).json()["id"]
    assert client.post(
        "/portal/secondary-requests",
        json={"entity_id": eid, "security_class_id": sc, "quantity": 10, "price_per_unit": "-50"},
        headers=h,
    ).status_code == 422


def test_fee_charge_as_of_clamped_to_today(client):
    h = auth_headers(client)
    tid = client.post("/tenants", json={"name": "G2", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "G2 Fund", "type": "fund"}, headers=h
    ).json()["id"]
    fid = client.post(f"/entities/{eid}/fund", json={"sebi_category": "II"}, headers=h).json()["id"]
    client.post(f"/funds/{fid}/lps", json={"name": "LP", "commitment": "10000000"}, headers=h)
    # LP admitted today: a future as_of must NOT charge next year's fees
    future = (today_ist() + dt.timedelta(days=365)).isoformat()
    r = client.post(f"/funds/{fid}/fees/charge?as_of={future}", headers=h).json()
    assert r["charged"] == "0.00"


def test_csv_export_neutralises_formulas(client):
    h = auth_headers(client)
    tid = client.post("/tenants", json={"name": "C", "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "C Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Eq", "kind": "equity"}, headers=h
    ).json()["id"]
    evil = client.post(
        f"/entities/{eid}/stakeholders",
        json={"name": "=HYPERLINK(\"http://evil\")", "type": "investor"},
        headers=h,
    ).json()["id"]
    client.post(
        f"/entities/{eid}/issuances",
        json={"security_class_id": sc, "stakeholder_id": evil, "quantity": 10,
              "price_per_unit": "1", "issue_date": "2026-01-01"},
        headers=h,
    )
    out = client.get(f"/entities/{eid}/cap-table.csv", headers=h).text
    assert "'=HYPERLINK" in out and '\n"=HYPERLINK' not in out


def test_import_row_cap(client):
    h = auth_headers(client)
    tid = client.post("/tenants", json={"name": "I", "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "I Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    csv_text = "stakeholder_name,security_class,quantity\n" + "".join(
        f"P{i},Eq,1\n" for i in range(10_001)
    )
    r = client.post(f"/entities/{eid}/cap-table/import", json={"csv": csv_text}, headers=h).json()
    assert not r["valid"] and "Too many rows" in r["errors"][0]["error"]

def test_email_case_insensitive_registration_and_login(client):
    """Registration + login normalise the email, so casing/whitespace can't
    create duplicate accounts or lock a user out."""
    r = client.post(
        "/auth/signup",
        json={"email": "  Casey@Example.IN ", "full_name": "Casey", "password": "pw12345678"},
    )
    assert r.status_code == 201
    assert r.json()["email"] == "casey@example.in"  # stored normalised
    # a differently-cased duplicate cannot create a second account
    dup = client.post(
        "/auth/signup",
        json={"email": "CASEY@example.in", "full_name": "Casey2", "password": "pw12345678"},
    )
    assert dup.status_code == 409
    # login succeeds whatever case is typed
    tok = client.post("/auth/login", json={"email": "CASEY@EXAMPLE.IN", "password": "pw12345678"})
    assert tok.status_code == 200 and tok.json()["access_token"]


def test_advisor_grant_email_normalised(client):
    """Cross-tenant advisor grants store a normalised email, so the match to the
    advisor's login identity is deterministic (no case-based bypass/miss)."""
    h = auth_headers(client, email="owner@advtest.in")
    tid = client.post("/tenants", json={"name": "Adv Co", "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Adv Co Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    g = client.post(
        f"/entities/{eid}/advisor-access",
        json={"email": "Advisor@Firm.IN", "firm_name": "Trilegal", "role": "viewer"},
        headers=h,
    )
    assert g.status_code == 201
    assert g.json()["email"] == "advisor@firm.in"


def test_logout_revokes_outstanding_token(client):
    """Logout bumps the user's token_version, so previously-issued JWTs are
    rejected server-side (stateless revocation) — not just cleared client-side."""
    h = auth_headers(client, email="revoke@test.in")
    assert client.get("/tenants", headers=h).status_code == 200  # token valid
    assert client.post("/auth/logout", headers=h).status_code == 204
    assert client.get("/tenants", headers=h).status_code == 401  # same token now revoked


def test_list_endpoints_are_paginated(client):
    """Large collections are bounded: default returns a page, explicit
    limit/offset paginate, and an over-cap limit is clamped (<= 500)."""
    h = auth_headers(client, email="page@test.in")
    tid = client.post("/tenants", json={"name": "P", "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "P Co", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    for i in range(7):
        client.post(
            f"/entities/{eid}/stakeholders", json={"name": f"SH{i}", "type": "founder"}, headers=h
        )
    all_rows = client.get(f"/entities/{eid}/stakeholders", headers=h).json()
    assert len(all_rows) == 7  # under the default page size
    assert len(client.get(f"/entities/{eid}/stakeholders?limit=3", headers=h).json()) == 3
    assert len(client.get(f"/entities/{eid}/stakeholders?limit=3&offset=6", headers=h).json()) == 1
    # over-cap limit is clamped, never unbounded
    assert len(client.get(f"/entities/{eid}/stakeholders?limit=99999", headers=h).json()) == 7
