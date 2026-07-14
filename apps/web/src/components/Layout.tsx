import { useEffect, useState } from "react";
import { Link, Outlet } from "react-router-dom";
import { api, type AppNotification } from "../api";
import { useAuth } from "../auth";

export default function Layout() {
  const { user, logout } = useAuth();
  const [notifs, setNotifs] = useState<AppNotification[]>([]);
  const [open, setOpen] = useState(false);

  const load = () => api.notifications().then(setNotifs).catch(() => {});
  useEffect(() => {
    load();
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
        <span className="spacer" />
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
    </>
  );
}
