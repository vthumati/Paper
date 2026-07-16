import { useEffect, useRef, useState } from "react";

/** A promise-based replacement for window.prompt(), which embedded browsers
 * (and some webviews) block outright. uiPrompt() shows an in-app dialog and
 * resolves to the entered string, or null if cancelled. Falls back to the
 * native prompt only if the host isn't mounted. */
type PromptReq = {
  message: string;
  defaultValue: string;
  resolve: (value: string | null) => void;
};

let emit: ((req: PromptReq) => void) | null = null;

export function uiPrompt(message: string, defaultValue = ""): Promise<string | null> {
  return new Promise((resolve) => {
    if (emit) emit({ message, defaultValue, resolve });
    else resolve(window.prompt(message, defaultValue));
  });
}

export default function PromptHost() {
  const [req, setReq] = useState<PromptReq | null>(null);
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    emit = (r) => {
      setReq(r);
      setValue(r.defaultValue);
      setTimeout(() => inputRef.current?.select(), 20);
    };
    return () => {
      emit = null;
    };
  }, []);

  if (!req) return null;
  const close = (v: string | null) => {
    req.resolve(v);
    setReq(null);
  };

  return (
    <div className="modal-overlay" onClick={() => close(null)}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()}>
        <p style={{ margin: "0 0 12px" }}>{req.message}</p>
        <input
          ref={inputRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") close(value);
            if (e.key === "Escape") close(null);
          }}
        />
        <div className="row" style={{ justifyContent: "flex-end", gap: 8, marginTop: 14 }}>
          <button className="secondary" style={{ flex: "0 0 auto" }} onClick={() => close(null)}>
            Cancel
          </button>
          <button style={{ flex: "0 0 auto" }} onClick={() => close(value)}>
            OK
          </button>
        </div>
      </div>
    </div>
  );
}
