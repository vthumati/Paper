import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api, type AppNotification, type Entity } from "../api";
import { useAuth } from "../auth";
import CommandPalette from "./CommandPalette";

const NAV = [
  { to: "/", label: "Home", icon: "🏠", end: true },
  { to: "/portal", label: "Portal", icon: "💼", end: false },
  { to: "/advisor", label: "Advisor", icon: "🤝", end: false },
  { to: "/activity", label: "Activity", icon: "🕘", end: false },
  { to: "/guide", label: "Guide", icon: "📖", end: false },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [notifs, setNotifs] = useState<AppNotification[]>([]);
  const [bellOpen, setBellOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const [switcherOpen, setSwitcherOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [theme, setTheme] = useState(
    () => document.documentElement.dataset.theme || "light"
  );
  const [workspaces, setWorkspaces] = useState<(Entity & { tenant_name: string })[]>([]);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("paper_theme", next);
    setTheme(next);
  };

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

  // close mobile nav / popovers on route change
  useEffect(() => {
    setNavOpen(false);
    setSwitcherOpen(false);
    setBellOpen(false);
  }, [loc.pathname]);

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

  const crumb =
    NAV.find((n) => (n.end ? loc.pathname === n.to : loc.pathname.startsWith(n.to)))?.label ??
    (loc.pathname.startsWith("/entities") || loc.pathname.startsWith("/tenants")
      ? "Workspace"
      : "Paper");

  return (
    <div className={`app-shell${navOpen ? " nav-open" : ""}`}>
      <div className="sb-scrim" onClick={() => setNavOpen(false)} />

      <aside className="sidebar">
        <NavLink to="/" className="brand">
          <span className="brand-mark">P</span>
          Paper
        </NavLink>

        <div className="side-section">Menu</div>
        {NAV.map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            end={n.end}
            className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
          >
            <span className="nav-ico">{n.icon}</span>
            {n.label}
          </NavLink>
        ))}

        <div className="side-section">Workspaces</div>
        <button
          className="nav-link"
          onClick={() => {
            const next = !switcherOpen;
            setSwitcherOpen(next);
            if (next && workspaces.length === 0) loadWorkspaces();
          }}
        >
          <span className="nav-ico">🗂️</span>
          Switch workspace
          <span className="nav-ico" style={{ marginLeft: "auto" }}>
            {switcherOpen ? "▾" : "▸"}
          </span>
        </button>
        {switcherOpen && (
          <div style={{ maxHeight: 240, overflowY: "auto", paddingBottom: 4 }}>
            {workspaces.length === 0 ? (
              <div className="nav-link" style={{ opacity: 0.6, fontSize: 13 }}>
                Loading…
              </div>
            ) : (
              workspaces.map((w) => (
                <button
                  key={w.id}
                  className="nav-link"
                  style={{ fontSize: 13, paddingLeft: 12 }}
                  onClick={() => nav(`/entities/${w.id}`)}
                  title={`${w.name} · ${w.tenant_name}`}
                >
                  <span className="avatar">{w.name.charAt(0).toUpperCase()}</span>
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {w.name}
                  </span>
                </button>
              ))
            )}
          </div>
        )}

        <span className="spacer" />

        <div className="side-foot">
          <button className="nav-link" onClick={toggleTheme}>
            <span className="nav-ico">{theme === "dark" ? "☀️" : "🌙"}</span>
            {theme === "dark" ? "Light mode" : "Dark mode"}
          </button>
          <button className="nav-link" onClick={logout}>
            <span className="nav-ico">↪</span>
            Log out
          </button>
          <div className="side-user">
            <span className="side-avatar">
              {(user?.full_name || "?").charAt(0).toUpperCase()}
            </span>
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {user?.full_name}
            </span>
          </div>
        </div>
      </aside>

      <div className="app-main">
        <header className="app-header">
          <button className="side-toggle" onClick={() => setNavOpen(true)} title="Menu">
            ☰
          </button>
          <span className="crumb">
            <strong>{crumb}</strong>
          </span>
          <span className="spacer" />
          <button className="header-btn" onClick={() => setPaletteOpen(true)} title="Quick search">
            🔍 Search <kbd>⌘K</kbd>
          </button>
          <div style={{ position: "relative" }}>
            <button
              className="header-btn"
              onClick={() => {
                setBellOpen(!bellOpen);
                if (!bellOpen) load();
              }}
              title="Notifications"
            >
              🔔 {unread > 0 && <span className="nav-badge">{unread}</span>}
            </button>
            {bellOpen && (
              <div
                style={{
                  position: "absolute",
                  right: 0,
                  top: 46,
                  width: 340,
                  maxHeight: 440,
                  overflowY: "auto",
                  background: "var(--panel)",
                  color: "var(--text)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius)",
                  padding: 14,
                  zIndex: 50,
                  boxShadow: "var(--shadow-md)",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <strong style={{ color: "var(--heading)" }}>Notifications</strong>
                  {unread > 0 && (
                    <button className="ghost" onClick={markAll}>
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
                        padding: "9px 0",
                        opacity: n.read ? 0.55 : 1,
                      }}
                    >
                      <div style={{ fontSize: 13, fontWeight: 650 }}>{n.title}</div>
                      {n.body && <div className="muted">{n.body}</div>}
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        </header>

        <div className="container">
          <Outlet />
        </div>
      </div>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  );
}
