import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, type Entity, type FileItem } from "../api";

const TAB_JUMPS: { key: string; label: string }[] = [
  { key: "dashboard", label: "Dashboard" },
  { key: "captable", label: "Cap Table" },
  { key: "esop", label: "ESOP" },
  { key: "valuations", label: "Valuations" },
  { key: "fundraising", label: "Rounds & SAFEs" },
  { key: "diligence", label: "Diligence" },
  { key: "investors", label: "Investors" },
  { key: "governance", label: "Board & Resolutions" },
  { key: "compliance", label: "Compliance" },
  { key: "registers", label: "Registers" },
  { key: "startup", label: "Startup India" },
  { key: "team", label: "Team" },
  { key: "contracts", label: "Contracts" },
  { key: "finance", label: "Finance" },
  { key: "documents", label: "Documents" },
  { key: "services", label: "Marketplace" },
  { key: "admin", label: "Managed Admin" },
  { key: "capital", label: "Fund · Capital & LPs" },
  { key: "fundraise", label: "Fund · LP fundraise" },
  { key: "portfolio", label: "Fund · Portfolio" },
  { key: "monitoring", label: "Fund · Monitoring" },
  { key: "deals", label: "Fund · Deal pipeline" },
  { key: "plan", label: "Fund · Plan & forecast" },
  { key: "reports", label: "Fund · Financials" },
  { key: "spv", label: "SPV" },
];

interface Item {
  id: string;
  label: string;
  hint: string;
  run: () => void;
}

/** Ctrl/⌘-K quick search: jump to any entity, any tab of the current
 * workspace, or search the current entity's documents. */
export default function CommandPalette({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const nav = useNavigate();
  const location = useLocation();
  const [q, setQ] = useState("");
  const [idx, setIdx] = useState(0);
  const [entities, setEntities] = useState<(Entity & { tenant_name: string })[]>([]);
  const [docs, setDocs] = useState<FileItem[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  const entityId = location.pathname.startsWith("/entities/")
    ? location.pathname.split("/")[2]
    : null;

  // load the entity directory once per open
  useEffect(() => {
    if (!open) return;
    setQ("");
    setIdx(0);
    setDocs([]);
    setTimeout(() => inputRef.current?.focus(), 30);
    api
      .listTenants()
      .then(async (tenants) => {
        const all = await Promise.all(
          tenants.map(async (t) => {
            const es = await api.listEntities(t.id).catch(() => []);
            return es.map((e) => ({ ...e, tenant_name: t.name }));
          })
        );
        setEntities(all.flat());
      })
      .catch(() => {});
  }, [open]);

  // document search within the current entity (debounced)
  useEffect(() => {
    if (!open || !entityId || q.trim().length < 3) {
      setDocs([]);
      return;
    }
    const h = setTimeout(() => {
      api.files(entityId, q.trim()).then((f) => setDocs(f.slice(0, 5))).catch(() => {});
    }, 250);
    return () => clearTimeout(h);
  }, [q, open, entityId]);

  const items = useMemo<Item[]>(() => {
    const needle = q.trim().toLowerCase();
    const match = (s: string) => !needle || s.toLowerCase().includes(needle);
    const out: Item[] = [];
    if (entityId) {
      for (const t of TAB_JUMPS.filter((t) => match(t.label))) {
        out.push({
          id: `tab-${t.key}`,
          label: t.label,
          hint: "Go to tab",
          run: () => nav(`/entities/${entityId}?tab=${t.key}`),
        });
      }
    }
    for (const e of entities.filter((e) => match(e.name))) {
      out.push({
        id: `ent-${e.id}`,
        label: e.name,
        hint: `Open workspace · ${e.tenant_name}`,
        run: () => nav(`/entities/${e.id}`),
      });
    }
    for (const d of docs) {
      out.push({
        id: `doc-${d.id}`,
        label: d.title,
        hint: "Document — open Documents tab",
        run: () => nav(`/entities/${entityId}?tab=documents`),
      });
    }
    return out.slice(0, 10);
  }, [q, entities, docs, entityId, nav]);

  useEffect(() => setIdx(0), [q]);

  if (!open) return null;

  const pick = (item: Item) => {
    item.run();
    onClose();
  };

  return (
    <div className="palette-overlay" onClick={onClose}>
      <div className="palette" onClick={(e) => e.stopPropagation()}>
        <input
          ref={inputRef}
          placeholder="Jump to an entity, tab, or document…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") onClose();
            if (e.key === "ArrowDown") { e.preventDefault(); setIdx((i) => Math.min(i + 1, items.length - 1)); }
            if (e.key === "ArrowUp") { e.preventDefault(); setIdx((i) => Math.max(i - 1, 0)); }
            if (e.key === "Enter" && items[idx]) pick(items[idx]);
          }}
        />
        <div className="palette-results">
          {items.length === 0 && <div className="muted" style={{ padding: 10 }}>No matches.</div>}
          {items.map((item, i) => (
            <div
              key={item.id}
              className={`palette-item ${i === idx ? "active" : ""}`}
              onMouseEnter={() => setIdx(i)}
              onClick={() => pick(item)}
            >
              <span>{item.label}</span>
              <span className="muted">{item.hint}</span>
            </div>
          ))}
        </div>
        <div className="palette-foot muted">↑↓ navigate · Enter select · Esc close</div>
      </div>
    </div>
  );
}
