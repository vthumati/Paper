"""Visible-style investor updates (FR-K-2 extended): structured sections,
metrics snapshot at publish, draft lifecycle, and per-viewer engagement."""
from tests.conftest import auth_headers


def _company_with_investor(client, owner):
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=owner).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"}, headers=owner
    ).json()["id"]
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Equity", "kind": "equity"}, headers=owner
    ).json()["id"]
    inv = client.post(
        f"/entities/{eid}/stakeholders",
        json={"name": "Seed Fund", "type": "investor", "email": "lp@seedfund.in"},
        headers=owner,
    ).json()["id"]
    client.post(
        f"/entities/{eid}/issuances",
        json={"security_class_id": sc, "stakeholder_id": inv, "quantity": 2000, "price_per_unit": "100", "issue_date": "2026-01-01"},
        headers=owner,
    )
    client.post(
        f"/entities/{eid}/investor-access",
        json={"email": "lp@seedfund.in", "stakeholder_id": inv},
        headers=owner,
    )
    return eid


def test_draft_then_publish_captures_metrics(client):
    owner = auth_headers(client, email="founder@acme.in")
    eid = _company_with_investor(client, owner)
    upd = client.post(
        f"/entities/{eid}/investor-updates",
        json={
            "title": "Q1 FY27 update",
            "body": "Steady quarter.",
            "period_label": "Q1 FY27",
            "highlights": "Closed 3 enterprise logos.",
            "lowlights": "Hiring slower than planned.",
            "asks": "Intros to CFOs.",
            "publish": False,
        },
        headers=owner,
    ).json()
    assert upd["status"] == "draft" and upd["metrics"] is None

    # drafts are invisible in the investor portal
    investor = auth_headers(client, email="lp@seedfund.in")
    entry = client.get("/portal", headers=investor).json()["companies"][0]
    assert entry["updates"] == []

    # drafts can be edited (full replace); publishing freezes a metrics snapshot
    edited = client.put(
        f"/investor-updates/{upd['id']}",
        json={
            "title": "Q1 FY27 update",
            "body": "Strong quarter.",
            "period_label": "Q1 FY27",
            "highlights": "Closed 3 enterprise logos.",
            "lowlights": "Hiring slower than planned.",
            "asks": "Intros to CFOs.",
        },
        headers=owner,
    )
    assert edited.status_code == 200 and edited.json()["body"] == "Strong quarter."
    pub = client.post(f"/investor-updates/{upd['id']}/publish", headers=owner).json()
    assert pub["status"] == "published" and pub["published_at"] is not None
    assert pub["metrics"]["shares_issued"] == 2000

    # published updates can be neither edited nor re-published
    assert (
        client.put(
            f"/investor-updates/{upd['id']}",
            json={"title": "x", "body": "y"},
            headers=owner,
        ).status_code
        == 409
    )
    assert client.post(f"/investor-updates/{upd['id']}/publish", headers=owner).status_code == 409

    entry = client.get("/portal", headers=investor).json()["companies"][0]
    assert len(entry["updates"]) == 1
    assert entry["updates"][0]["highlights"] == "Closed 3 enterprise logos."


def test_view_tracking_counts_repeat_opens(client):
    owner = auth_headers(client, email="founder@acme.in")
    eid = _company_with_investor(client, owner)
    upd = client.post(
        f"/entities/{eid}/investor-updates",
        json={"title": "Q2 update", "body": "Revenue up 30%."},
        headers=owner,
    ).json()
    assert upd["status"] == "published" and upd["metrics"] is not None

    investor = auth_headers(client, email="lp@seedfund.in")
    assert client.post(f"/portal/updates/{upd['id']}/view", headers=investor).json()["view_count"] == 1
    assert client.post(f"/portal/updates/{upd['id']}/view", headers=investor).json()["view_count"] == 2

    rows = client.get(f"/entities/{eid}/investor-updates", headers=owner).json()
    assert rows[0]["viewers"] == [
        {
            "email": "lp@seedfund.in",
            "view_count": 2,
            "last_viewed_at": rows[0]["viewers"][0]["last_viewed_at"],
        }
    ]


def test_uninvited_user_cannot_record_views(client):
    owner = auth_headers(client, email="founder@acme.in")
    eid = _company_with_investor(client, owner)
    upd = client.post(
        f"/entities/{eid}/investor-updates",
        json={"title": "Q2 update", "body": "Revenue up 30%."},
        headers=owner,
    ).json()
    stranger = auth_headers(client, email="stranger@nowhere.in")
    assert client.post(f"/portal/updates/{upd['id']}/view", headers=stranger).status_code == 404
