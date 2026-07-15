"""External advisor workspace (FR-J-2, Mantle gap): a company grants a law
firm / CA scoped, cross-tenant access to its entity; deps._entity_role then
lets that advisor act at their granted level without tenant membership."""
from tests.conftest import auth_headers


def _company(client, h, name="Co"):
    tid = client.post("/tenants", json={"name": name, "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": f"{name} Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    return tid, eid


def test_advisor_member_can_act(client):
    founder = auth_headers(client, email="founder@co.in")
    _, eid = _company(client, founder)
    # a stranger (no membership) is blocked before the grant
    lawyer = auth_headers(client, email="lawyer@firm.in")
    assert client.get(f"/entities/{eid}/security-classes", headers=lawyer).status_code == 403

    # company grants the firm 'member' (acting) access
    r = client.post(
        f"/entities/{eid}/advisor-access",
        json={"email": "lawyer@firm.in", "firm_name": "Trilegal", "role": "member"},
        headers=founder,
    )
    assert r.status_code == 201, r.text
    assert r.json()["role"] == "member"

    # now the advisor can read AND write entity resources
    assert client.get(f"/entities/{eid}/security-classes", headers=lawyer).status_code == 200
    made = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Equity", "kind": "equity"}, headers=lawyer
    )
    assert made.status_code == 201, made.text


def test_advisor_viewer_is_readonly(client):
    founder = auth_headers(client, email="founder2@co.in")
    _, eid = _company(client, founder, name="Ro")
    ca = auth_headers(client, email="ca@audit.in")
    client.post(
        f"/entities/{eid}/advisor-access",
        json={"email": "ca@audit.in", "firm_name": "SR Batliboi", "role": "viewer"},
        headers=founder,
    )
    # read OK
    assert client.get(f"/entities/{eid}/documents", headers=ca).status_code == 200
    # write blocked (viewer not in WRITE_ROLES)
    w = client.post(
        f"/entities/{eid}/security-classes", json={"name": "X", "kind": "equity"}, headers=ca
    )
    assert w.status_code == 403


def test_advisor_console_cross_tenant(client):
    # two different founders/tenants both hire the same advisor
    f1 = auth_headers(client, email="f1@x.in")
    _, e1 = _company(client, f1, name="Alpha")
    f2 = auth_headers(client, email="f2@y.in")
    _, e2 = _company(client, f2, name="Beta")
    for f, e in [(f1, e1), (f2, e2)]:
        client.post(
            f"/entities/{e}/advisor-access",
            json={"email": "partner@cs.in", "firm_name": "CS Associates", "role": "viewer"},
            headers=f,
        )
    adv = auth_headers(client, email="partner@cs.in")
    console = client.get("/advisor/entities", headers=adv).json()
    names = {c["entity_name"] for c in console}
    assert names == {"Alpha Pvt Ltd", "Beta Pvt Ltd"}
    assert all(c["firm_name"] == "CS Associates" for c in console)


def test_advisor_revoke(client):
    founder = auth_headers(client, email="founder3@co.in")
    _, eid = _company(client, founder, name="Gamma")
    adv_id = client.post(
        f"/entities/{eid}/advisor-access",
        json={"email": "temp@firm.in", "firm_name": "Temp", "role": "member"},
        headers=founder,
    ).json()["id"]
    temp = auth_headers(client, email="temp@firm.in")
    assert client.get(f"/entities/{eid}/documents", headers=temp).status_code == 200
    # revoke
    assert client.delete(f"/entities/{eid}/advisor-access/{adv_id}", headers=founder).status_code == 204
    assert client.get(f"/entities/{eid}/documents", headers=temp).status_code == 403
    assert client.get("/advisor/entities", headers=temp).json() == []


def test_advisor_grant_requires_write(client):
    founder = auth_headers(client, email="founder4@co.in")
    _, eid = _company(client, founder, name="Delta")
    # a viewer-advisor cannot grant further access
    client.post(
        f"/entities/{eid}/advisor-access",
        json={"email": "v@firm.in", "firm_name": "V", "role": "viewer"},
        headers=founder,
    )
    viewer = auth_headers(client, email="v@firm.in")
    r = client.post(
        f"/entities/{eid}/advisor-access",
        json={"email": "x@firm.in", "firm_name": "X", "role": "member"},
        headers=viewer,
    )
    assert r.status_code == 403
