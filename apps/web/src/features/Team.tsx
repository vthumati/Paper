import { useEffect, useState } from "react";
import { useGuard } from "../hooks";
import { api, type TeamMember } from "../api";
import EmptyState from "../components/EmptyState";
import PageHeader from "../components/PageHeader";

export default function Team({ entityId }: { entityId: string }) {
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [note, setNote] = useState("");
  const { error, setError, guard } = useGuard(() => load());

  const [name, setName] = useState("");
  const [title, setTitle] = useState("");
  const [type, setType] = useState("employee");

  const load = () => api.listTeam(entityId).then(setMembers).catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, [entityId]);

  return (
    <div>
      <PageHeader
        icon="👥"
        title="Team"
        subtitle="Employees, contractors and advisors — onboard to generate HR docs and link to the cap table."
        right={<span className="badge">{members.length} member{members.length === 1 ? "" : "s"}</span>}
      />
      {error && <p className="error">{error}</p>}
      {note && <p className="muted">{note}</p>}

      <div className="card">
        <h3>Add team member</h3>
        <div className="row">
          <input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
          <input placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
          <select value={type} onChange={(e) => setType(e.target.value)}>
            <option value="employee">Employee</option>
            <option value="contractor">Contractor</option>
            <option value="advisor">Advisor</option>
          </select>
          <button
            style={{ flex: "0 0 auto" }}
            disabled={!name}
            onClick={guard(async () => {
              await api.addTeamMember(entityId, { name, title, employment_type: type });
              setName(""); setTitle("");
            })}
          >
            Add
          </button>
        </div>
      </div>

      <div className="card">
        <h3>Team</h3>
        {members.length === 0 ? (
          <EmptyState icon="👥" title="No team members yet" hint="Add employees, contractors and advisors above — onboarding generates HR documents and links them to the cap table." />
        ) : (
          <table>
            <thead>
              <tr><th>Name</th><th>Title</th><th>Type</th><th>Status</th><th>Cap table</th><th></th></tr>
            </thead>
            <tbody>
              {members.map((m) => (
                <tr key={m.id}>
                  <td>{m.name}</td>
                  <td>{m.title || "—"}</td>
                  <td>{m.employment_type}</td>
                  <td><span className={`badge ${m.status === "active" ? "complete" : "skipped"}`}>{m.status}</span></td>
                  <td>{m.stakeholder_id ? <span className="badge">linked</span> : <span className="muted">—</span>}</td>
                  <td>
                    {!m.stakeholder_id && (
                      <button
                        className="secondary"
                        onClick={guard(async () => {
                          const r = await api.onboardMember(m.id);
                          setNote(`Onboarded ${m.name}: ${r.documents.length} HR documents generated (see Files) and added to the cap table for ESOP.`);
                        })}
                      >
                        Onboard
                      </button>
                    )}{" "}
                    {m.status === "active" && (
                      <button
                        className="secondary"
                        onClick={guard(async () => {
                          const left = window.prompt(
                            "Leaving date (YYYY-MM-DD) — unvested options lapse back to the pool:",
                            new Date().toISOString().slice(0, 10)
                          );
                          if (!left) return;
                          const r = await api.offboardMember(m.id, { left_on: left });
                          setNote(
                            `${m.name} offboarded.` +
                              (r.lapsed_options
                                ? ` ${r.lapsed_options.toLocaleString()} unvested option(s) lapsed back to the pool across ${r.grants_affected} grant(s).`
                                : " No unvested options to lapse.")
                          );
                        })}
                      >
                        Offboard
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
