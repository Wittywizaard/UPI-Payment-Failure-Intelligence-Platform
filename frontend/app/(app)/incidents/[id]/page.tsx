"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, XCircle } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { useAuth, CAN_WRITE_ROLES } from "@/lib/auth-context";
import { formatDateTime, formatInr, formatNumber, formatPct, SEVERITY_COLORS, STATUS_COLORS } from "@/lib/format";
import type { IncidentDetail, IncidentStatus } from "@/lib/types";

const TRANSITIONS: Record<IncidentStatus, IncidentStatus[]> = {
  open: ["investigating", "closed"],
  investigating: ["mitigated", "open", "closed"],
  mitigated: ["resolved", "investigating"],
  resolved: ["closed", "investigating"],
  closed: [],
};

export default function IncidentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const [incident, setIncident] = useState<IncidentDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [note, setNote] = useState("");

  const canWrite = user ? CAN_WRITE_ROLES.includes(user.role) : false;

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.get<IncidentDetail>(`/api/incidents/${id}`);
      setIncident(resp);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load incident.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function handleTransition(newStatus: IncidentStatus) {
    setUpdating(true);
    setError(null);
    try {
      const updated = await api.patch<IncidentDetail>(`/api/incidents/${id}`, { status: newStatus });
      setIncident(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update status.");
    } finally {
      setUpdating(false);
    }
  }

  async function handleAddNote() {
    if (!note.trim()) return;
    setUpdating(true);
    try {
      const updated = await api.patch<IncidentDetail>(`/api/incidents/${id}`, { note });
      setIncident(updated);
      setNote("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to add note.");
    } finally {
      setUpdating(false);
    }
  }

  if (loading) return <div className="p-6 max-w-[1000px] mx-auto"><div className="card h-48 bg-bg-surface-raised animate-pulse" /></div>;
  if (error && !incident) {
    return (
      <div className="p-6 max-w-[1000px] mx-auto">
        <div className="card border-critical/40 bg-critical/5 px-4 py-3 text-sm text-critical flex items-center gap-2">
          <XCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      </div>
    );
  }
  if (!incident) return null;

  return (
    <div className="p-6 max-w-[1000px] mx-auto">
      <button onClick={() => router.push("/incidents")} className="btn-ghost text-sm mb-4">
        <ArrowLeft className="w-3.5 h-3.5" />
        Back to Incidents
      </button>

      <div className="card p-5 mb-4">
        <div className="flex items-center gap-2 mb-2">
          <span className={`badge ${SEVERITY_COLORS[incident.severity]}`}>{incident.severity}</span>
          <span className={`badge ${STATUS_COLORS[incident.status]}`}>{incident.status}</span>
        </div>
        <h1 className="text-lg font-semibold text-text-primary mb-4">{incident.title}</h1>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
          <div>
            <div className="text-xs text-text-tertiary mb-1">Observed PSR</div>
            <div className="text-lg font-semibold numeric text-critical">{formatPct(incident.observed_psr)}</div>
          </div>
          <div>
            <div className="text-xs text-text-tertiary mb-1">Baseline PSR</div>
            <div className="text-lg font-semibold numeric">{formatPct(incident.baseline_psr)}</div>
          </div>
          <div>
            <div className="text-xs text-text-tertiary mb-1">Affected Txns</div>
            <div className="text-lg font-semibold numeric">{formatNumber(incident.affected_transactions)}</div>
          </div>
          <div>
            <div className="text-xs text-text-tertiary mb-1">Value at Risk</div>
            <div className="text-lg font-semibold numeric text-warning">
              {incident.estimated_value_at_risk ? formatInr(incident.estimated_value_at_risk) : "—"}
            </div>
          </div>
        </div>

        {incident.affected_fingerprint && (
          <div className="mb-4">
            <div className="text-xs text-text-tertiary mb-1">FAILURE FINGERPRINT</div>
            <div className="numeric text-sm text-text-primary">
              {Object.values(incident.affected_fingerprint).join(" × ")}
            </div>
          </div>
        )}

        {canWrite && incident.status !== "closed" && (
          <div className="flex items-center gap-2 pt-3 border-t border-border">
            <span className="text-xs text-text-tertiary mr-1">Move to:</span>
            {TRANSITIONS[incident.status].map((next) => (
              <button key={next} onClick={() => handleTransition(next)} disabled={updating} className="btn-secondary text-xs">
                {next}
              </button>
            ))}
          </div>
        )}
      </div>

      {error && (
        <div className="card border-critical/40 bg-critical/5 px-4 py-3 mb-4 text-sm text-critical flex items-center gap-2">
          <XCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      <div className="card p-5 mb-4">
        <div className="text-xs text-text-tertiary mb-3">LINKED INTERVENTIONS ({incident.interventions.length})</div>
        {incident.interventions.length === 0 && (
          <p className="text-sm text-text-tertiary">No interventions yet.</p>
        )}
        <div className="space-y-2">
          {incident.interventions.map((iv) => (
            <Link
              key={iv.intervention_id}
              href={`/interventions/${iv.intervention_id}`}
              className="flex items-center justify-between px-3 py-2.5 rounded-control border border-border hover:border-accent/50 hover:bg-bg-surface-hover"
            >
              <div>
                <div className="text-sm text-text-primary">{iv.type}</div>
                <div className="text-xs text-text-tertiary truncate max-w-md">{iv.hypothesis}</div>
              </div>
              <span className="badge bg-bg-surface-raised text-text-secondary border border-border">{iv.status}</span>
            </Link>
          ))}
        </div>
      </div>

      <div className="card p-5">
        <div className="text-xs text-text-tertiary mb-3">TIMELINE</div>
        <div className="space-y-3 mb-4">
          {incident.timeline.map((entry, i) => (
            <div key={i} className="flex gap-3 text-sm">
              <span className="numeric text-text-tertiary shrink-0 w-32">{formatDateTime(entry.timestamp)}</span>
              <span className="text-text-secondary">
                <span className="text-text-primary">{entry.action}</span>
                {typeof entry.metadata_json?.note === "string" && ` — "${entry.metadata_json.note}"`}
                {typeof entry.metadata_json?.actor === "string" && (
                  <span className="text-text-tertiary"> by {entry.metadata_json.actor}</span>
                )}
              </span>
            </div>
          ))}
        </div>

        {canWrite && (
          <div className="flex gap-2 pt-3 border-t border-border">
            <input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Add a note to the timeline..."
              className="input flex-1 text-sm"
            />
            <button onClick={handleAddNote} disabled={updating || !note.trim()} className="btn-secondary text-sm">
              Add Note
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
