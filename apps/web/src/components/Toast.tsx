import { useEffect, useState } from "react";

/** Lightweight global toast. Call `toast("Saved")` from anywhere; a stack
 * renders bottom-right and auto-dismisses. Same module-singleton pattern as
 * uiPrompt so non-component code can fire one. */
type Kind = "success" | "error" | "info";
type Toast = { id: number; msg: string; kind: Kind };

let emit: ((t: Toast) => void) | null = null;
let seq = 0;

export function toast(msg: string, kind: Kind = "success") {
  if (emit) emit({ id: ++seq, msg, kind });
}

export default function ToastHost() {
  const [items, setItems] = useState<Toast[]>([]);

  useEffect(() => {
    emit = (t) => {
      setItems((cur) => [...cur, t]);
      window.setTimeout(() => setItems((cur) => cur.filter((x) => x.id !== t.id)), 3600);
    };
    return () => {
      emit = null;
    };
  }, []);

  if (items.length === 0) return null;
  return (
    <div className="toast-stack">
      {items.map((t) => (
        <div
          key={t.id}
          className={`toast toast-${t.kind}`}
          role="status"
          onClick={() => setItems((cur) => cur.filter((x) => x.id !== t.id))}
        >
          <span className="toast-icon">
            {t.kind === "success" ? "✓" : t.kind === "error" ? "!" : "i"}
          </span>
          <span>{t.msg}</span>
        </div>
      ))}
    </div>
  );
}
