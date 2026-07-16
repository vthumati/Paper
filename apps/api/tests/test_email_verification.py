"""Email verification gate (SEC H-1) + admin-only access delegation (SEC M-1).

Dev leaves verification off (signups verified immediately), so the flag is
monkeypatched on here to exercise the enforced path.
"""
from app.config import settings
from app.db import SessionLocal
from app.models.identity import User
from tests.conftest import auth_headers


def _company(client, h, name="Co"):
    tid = client.post("/tenants", json={"name": name, "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": f"{name} Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    return tid, eid


def test_signup_verified_when_flag_off(client):
    r = client.post(
        "/auth/signup",
        json={"email": "dev@x.in", "full_name": "Dev", "password": "s3cret-pass"},
    )
    assert r.status_code == 201
    assert r.json()["email_verified"] is True


def test_unverified_email_blocks_portal_and_advisor(client, monkeypatch):
    monkeypatch.setattr(settings, "email_verification_required", True)
    r = client.post(
        "/auth/signup",
        json={"email": "lp@fund.in", "full_name": "LP", "password": "s3cret-pass"},
    )
    assert r.status_code == 201
    assert r.json()["email_verified"] is False
    token = client.post(
        "/auth/login", json={"email": "lp@fund.in", "password": "s3cret-pass"}
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    # email-matched surfaces are closed until the email is verified
    assert client.get("/portal", headers=h).status_code == 403
    assert client.get("/advisor/entities", headers=h).status_code == 403

    # complete verification with the stored token, then access opens up
    with SessionLocal() as db:
        vtoken = db.query(User).filter_by(email="lp@fund.in").first().email_verification_token
    assert vtoken
    v = client.post("/auth/verify-email", json={"token": vtoken})
    assert v.status_code == 200 and v.json()["email_verified"] is True
    assert client.get("/portal", headers=h).status_code == 200
    assert client.get("/advisor/entities", headers=h).status_code == 200


def test_verify_email_rejects_bad_token(client):
    assert client.post("/auth/verify-email", json={"token": "nope"}).status_code == 400


def test_member_advisor_cannot_grant_access(client):
    """A member-role advisor keeps write access but can no longer delegate
    further access — granting is owner/admin only (SEC M-1)."""
    founder = auth_headers(client, email="owner@co.in")
    _, eid = _company(client, founder, name="Zeta")
    client.post(
        f"/entities/{eid}/advisor-access",
        json={"email": "m@firm.in", "firm_name": "M&Co", "role": "member"},
        headers=founder,
    )
    member = auth_headers(client, email="m@firm.in")
    # still has write (can create a security class)
    assert client.post(
        f"/entities/{eid}/security-classes", json={"name": "Eq", "kind": "equity"}, headers=member
    ).status_code == 201
    # but cannot grant advisor or investor access
    assert client.post(
        f"/entities/{eid}/advisor-access",
        json={"email": "x@firm.in", "firm_name": "X", "role": "member"},
        headers=member,
    ).status_code == 403
    assert client.post(
        f"/entities/{eid}/investor-access", json={"email": "inv@vc.in"}, headers=member
    ).status_code == 403


def test_owner_can_grant_access(client):
    founder = auth_headers(client, email="owner2@co.in")
    _, eid = _company(client, founder, name="Eta")
    assert client.post(
        f"/entities/{eid}/investor-access", json={"email": "inv@vc.in"}, headers=founder
    ).status_code == 201
