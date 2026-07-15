import { useEffect, useState } from "react";
import { Link, Outlet, useNavigate } from "react-router-dom";
import { api, type AppNotification, type Entity } from "../api";
import { useAuth } from "../auth";
import CommandPalette from "./CommandPalette";

export default function Layout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [notifs, setNotifs] = useState<AppNotification[]>([]);
  const [open, setOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [workspaces, setWorkspaces] = useState<(Entity & { tenant_name: string })[]>([]);

  const loadWorkspaces = () =>
    api
      .listTenants()
      .then(async (tenants) => {
        const all = await Promise.all(
          tenants.map(async (t) => {
            const es = await api.listEntities(t.id).catch(() => []);
            return es.map((e) => ({ ...e, tenant_name: t.name }));
          })
        );
        setWorkspaces(all.flat());
      })
      .catch(() => {});

  const load = () => api.notifications().then(setNotifs).catch(() => {});
  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const unread = notifs.filter((n) => !n.read).length;

  async function markAll() {
    await api.markAllNotificationsRead();
    await load();
  }

  return (
    <>
      <div className="topbar">
        <Link to="/" className="brand">
          Paper
        </Link>
        <span className="muted" style={{ color: "#cbd5e1" }}>
          OS for corporate legal
        </span>
        <details className="actions-menu" onToggle={(e) => {
          if ((e.target as HTMLDetailsElement).open && workspaces.length === 0) loadWorkspaces();
        }}>
          <summary>Workspaces ▾</summary>
          <div className="actions-list" style={{ left: 0, right: "auto", maxHeight: 320, overflowY: "auto" }}>
            {workspaces.length === 0 && <span className="muted" style={{ padding: 4 }}>Loading…</span>}
            {workspaces.map((w) => (
              <button
                key={w.id}
                className="secondary"
                onClick={(ev) => {
                  (ev.currentTarget.closest("details") as HTMLDetailsElement).open = false;
                  nav(`/entities/${w.id}`);
                }}
              >
                <span className="avatar">{w.name.charAt(0).toUpperCase()}</span>{" "}
                {w.name} <span className="muted">· {w.tenant_name}</span>
              </button>
            ))}
          </div>
        </details>
        <span className="spacer" />
        <button className="secondary" onClick={() => setPaletteOpen(true)} title="Quick search">
          Search <span style={{ opacity: 0.7 }}>Ctrl K</span>
        </button>
        <Link to="/portal" style={{ fontSize: 14 }}>
          Portal
        </Link>
        <Link to="/activity" style={{ fontSize: 14 }}>
          Activity
        </Link>
        <div style={{ position: "relative" }}>
          <button
            className="secondary"
            onClick={() => {
              setOpen(!open);
              if (!open) load();
            }}
          >
            🔔 {unread > 0 ? `(${unread})` : ""}
          </button>
          {open && (
            <div
              style={{
                position: "absolute",
                right: 0,
                top: 40,
                width: 320,
                maxHeight: 400,
                overflowY: "auto",
                background: "#fff",
                color: "var(--text)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                padding: 10,
                zIndex: 10,
                boxShadow: "0 4px 16px rgba(0,0,0,0.15)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <strong style={{ color: "var(--navy)" }}>Notifications</strong>
                {unread > 0 && (
                  <button className="secondary" onClick={markAll}>
                    Mark all read
                  </button>
                )}
              </div>
              {notifs.length === 0 ? (
                <p className="muted">No notifications.</p>
              ) : (
                notifs.map((n) => (
                  <div
                    key={n.id}
                    style={{
                      borderTop: "1px solid var(--border)",
                      padding: "8px 0",
                      opacity: n.read ? 0.55 : 1,
                    }}
                  >
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{n.title}</div>
                    {n.body && <div className="muted">{n.body}</div>}
                  </div>
                ))
              )}
            </div>
          )}
        </div>
        <span style={{ fontSize: 14 }}>{user?.full_name}</span>
        <button className="secondary" onClick={logout}>
          Log out
        </button>
      </div>
      <div className="container">
        <Outlet />
      </div>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </>
  );
}
