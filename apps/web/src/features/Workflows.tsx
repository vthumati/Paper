import { useEffect, useState } from "react";
import { api, type WorkflowDefinition, type WorkflowRun } from "../api";

export default function Workflows({ entityId }: { entityId: string }) {
  const [defs, setDefs] = useState<WorkflowDefinition[]>([]);
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [selected, setSelected] = useState<WorkflowRun | null>(null);
  const [defKey, setDefKey] = useState("");
  const [output, setOutput] = useState("{}");
  const [error, setError] = useState("");

  async function load() {
    try {
      const [d, r] = await Promise.all([api.listDefinitions(), api.listRuns(entityId)]);
      setDefs(d);
      setRuns(r);
      if (!defKey && d.length) setDefKey(d[0].key);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    load();
  }, [entityId]);

  async function start() {
    setError("");
    try {
      const run = await api.startRun(entityId, { definition_key: defKey });
      setSelected(run);
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const activeStep = selected?.steps.find((s) => s.status === "active");

  async function complete() {
    if (!selected || !activeStep) return;
    setError("");
    let parsed: object;
    try {
      parsed = JSON.parse(output || "{}");
    } catch {
      setError("Output must be valid JSON");
      return;
    }
    try {
      const run = await api.completeStep(selected.id, activeStep.step_key, parsed);
      setSelected(run);
      setOutput("{}");
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  // hint payload for the document-generation step
  function hintFor(stepType: string): string {
    if (stepType === "generate_document")
      return JSON.stringify({ template_key: "sha", data: { company: "", investor: "" } }, null, 2);
    if (stepType === "collect_input") return JSON.stringify({ foreign_investor: false }, null, 2);
    return "{}";
  }

  return (
    <div>
      {error && <p className="error">{error}</p>}
      <div className="card">
        <h2>Start a workflow</h2>
        <div className="row">
          <select value={defKey} onChange={(e) => setDefKey(e.target.value)}>
            {defs.map((d) => (
              <option key={d.key} value={d.key}>{d.title}</option>
            ))}
          </select>
          <button style={{ flex: "0 0 auto" }} onClick={start} disabled={!defKey}>
            Start
          </button>
        </div>
      </div>

      <div className="row">
        <div className="card" style={{ flex: 1 }}>
          <h3>Runs</h3>
          {runs.length === 0 && <p className="muted">None yet.</p>}
          {runs.map((r) => (
            <div
              key={r.id}
              className={`list-item ${selected?.id === r.id ? "selected" : ""}`}
              onClick={() => api.getRun(r.id).then(setSelected)}
            >
              {r.title} <span className={`badge ${r.status}`}>{r.status}</span>
            </div>
          ))}
        </div>

        <div className="card" style={{ flex: 2 }}>
          <h3>Run detail</h3>
          {!selected ? (
            <p className="muted">Select a run.</p>
          ) : (
            <>
              <p>
                {selected.title} · <span className={`badge ${selected.status}`}>{selected.status}</span>
              </p>
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Step</th>
                    <th>Type</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {selected.steps.map((s) => (
                    <tr key={s.step_key}>
                      <td>{s.order_index + 1}</td>
                      <td>{s.title}</td>
                      <td className="muted">{s.type}</td>
                      <td><span className={`badge ${s.status}`}>{s.status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {Object.keys(selected.context).length > 0 && (
                <>
                  <h3>Context</h3>
                  <pre>{JSON.stringify(selected.context, null, 2)}</pre>
                </>
              )}

              {activeStep && (
                <div style={{ marginTop: 12 }}>
                  <h3>Complete: {activeStep.title}</h3>
                  <p className="muted">
                    Optional output JSON (folded into run context). Example for this step type:
                  </p>
                  <button
                    className="secondary"
                    type="button"
                    onClick={() => setOutput(hintFor(activeStep.type))}
                  >
                    Insert example
                  </button>
                  <textarea
                    rows={5}
                    value={output}
                    onChange={(e) => setOutput(e.target.value)}
                    style={{ marginTop: 8, fontFamily: "monospace" }}
                  />
                  <div style={{ marginTop: 10 }}>
                    <button onClick={complete}>Complete step</button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
