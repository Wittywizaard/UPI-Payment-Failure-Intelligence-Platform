"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, CheckCircle2, XCircle } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { useAuth, CAN_WRITE_ROLES } from "@/lib/auth-context";
import { formatPct } from "@/lib/format";
import type { Intervention } from "@/lib/types";

const DEFAULT_BEFORE_START = "2026-08-29T18:00";
const DEFAULT_BEFORE_END = "2026-08-29T20:00";
const DEFAULT_AFTER_START = "2026-08-29T20:00";
const DEFAULT_AFTER_END = "2026-08-29T22:00";

export default function InterventionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const [intervention, setIntervention] = useState<Intervention | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [measuring, setMeasuring] = useState(false);

  const [beforeStart, setBeforeStart] = useState(DEFAULT_BEFORE_START);
  const [beforeEnd, setBeforeEnd] = useState(DEFAULT_BEFORE_END);
  const [afterStart, setAfterStart] = useState(DEFAULT_AFTER_START);
  const [afterEnd, setAfterEnd] = useState(DEFAULT_AFTER_END);

  const canWrite = user ? CAN_WRITE_ROLES.includes(user.role) : false;

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.get<Intervention>(`/api/interventions/${id}`);
      setIntervention(resp);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load intervention.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function handleMeasure() {
    setMeasuring(true);
    setError(null);
    try {
      await api.post(`/api/interventions/${id}/measure-impact`, {
        before_start: `${beforeStart}:00`,
        before_end: `${beforeEnd}:00`,
        after_start: `${afterStart}:00`,
        after_end: `${afterEnd}:00`,
      });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to measure impact.");
    } finally {
      setMeasuring(false);
    }
  }

  async function handleMarkSuccessful() {
    try {
      const updated = await api.patch<Intervention>(`/api/interventions/${id}`, {
        status: "completed",
        outcome: "Successful",
      });
      setIntervention(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update intervention.");
    }
  }

  if (loading) return <div className="p-6 max-w-[900px] mx-auto"><div className="card h-48 bg-bg-surface-raised animate-pulse" /></div>;
  if (!intervention) {
    return (
      <div className="p-6 max-w-[900px] mx-auto">
        <div className="card border-critical/40 bg-critical/5 px-4 py-3 text-sm text-critical">{error}</div>
      </div>
    );
  }

  const impact = intervention.actual_impact;

  return (
    <div className="p-6 max-w-[900px] mx-auto">
      <button onClick={() => router.push(`/incidents/${intervention.incident_id}`)} className="btn-ghost text-sm mb-4">
        <ArrowLeft className="w-3.5 h-3.5" />
        Back to Incident
      </button>

      <div className="card p-5 mb-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="badge bg-bg-surface-raised text-text-secondary border border-border">{intervention.status}</span>
          <span className="text-xs text-text-tertiary numeric">{intervention.type}</span>
        </div>
        <h1 className="text-lg font-semibold text-text-primary mb-2">Intervention</h1>
        <p className="text-sm text-text-secondary mb-1">
          <span className="text-text-tertiary">Hypothesis: </span>
          {intervention.hypothesis}
        </p>
        {intervention.expected_impact && (
          <p className="text-sm text-text-secondary">
            <span className="text-text-tertiary">Expected impact: </span>
            {intervention.expected_impact}
          </p>
        )}
      </div>

      {error && (
        <div className="card border-critical/40 bg-critical/5 px-4 py-3 mb-4 text-sm text-critical flex items-center gap-2">
          <XCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {canWrite && (
        <div className="card p-5 mb-4">
          <div className="text-xs text-text-tertiary mb-3">MEASURE IMPACT</div>
          <div className="grid grid-cols-2 gap-4 mb-3">
            <div>
              <div className="text-xs text-text-secondary mb-1">Before window</div>
              <div className="flex gap-2">
                <input type="datetime-local" value={beforeStart} onChange={(e) => setBeforeStart(e.target.value)} className="input text-xs flex-1" />
                <input type="datetime-local" value={beforeEnd} onChange={(e) => setBeforeEnd(e.target.value)} className="input text-xs flex-1" />
              </div>
            </div>
            <div>
              <div className="text-xs text-text-secondary mb-1">After window</div>
              <div className="flex gap-2">
                <input type="datetime-local" value={afterStart} onChange={(e) => setAfterStart(e.target.value)} className="input text-xs flex-1" />
                <input type="datetime-local" value={afterEnd} onChange={(e) => setAfterEnd(e.target.value)} className="input text-xs flex-1" />
              </div>
            </div>
          </div>
          <button onClick={handleMeasure} disabled={measuring} className="btn-primary text-sm">
            {measuring ? "Measuring..." : "Measure Impact"}
          </button>
        </div>
      )}

      {impact && (
        <div className="card p-5 mb-4">
          <div className="text-xs text-text-tertiary mb-3">BEFORE / AFTER</div>
          <div className="grid grid-cols-2 gap-6">
            <div>
              <div className="text-xs text-text-secondary mb-2">BEFORE</div>
              <div className="text-2xl font-semibold numeric text-critical">{formatPct(impact.before.psr as number)}</div>
              <div className="text-xs text-text-tertiary mt-1">Recovery {formatPct(impact.before.recovery_rate as number)}</div>
            </div>
            <div>
              <div className="text-xs text-text-secondary mb-2">AFTER</div>
              <div className="text-2xl font-semibold numeric text-success">{formatPct(impact.after.psr as number)}</div>
              <div className="text-xs text-text-tertiary mt-1">Recovery {formatPct(impact.after.recovery_rate as number)}</div>
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-border flex items-center justify-between">
            <div className="text-sm">
              <span className="text-text-tertiary">Change: </span>
              <span className={`numeric font-medium ${(impact.delta.psr_pp as number) >= 0 ? "text-success" : "text-critical"}`}>
                {(impact.delta.psr_pp as number) >= 0 ? "+" : ""}
                {(impact.delta.psr_pp as number)?.toFixed(2)}pp PSR
              </span>
              <span className="text-text-tertiary mx-2">|</span>
              <span className="numeric text-text-secondary">
                {(impact.delta.recovery_rate_pp as number) >= 0 ? "+" : ""}
                {(impact.delta.recovery_rate_pp as number)?.toFixed(2)}pp Recovery
              </span>
            </div>
            <span
              className={`badge ${
                impact.guardrail_status === "within_threshold" ? "bg-success/15 text-success" : "bg-critical/15 text-critical"
              }`}
            >
              Guardrail: {impact.guardrail_status === "within_threshold" ? "Within threshold" : "Breached"}
            </span>
          </div>
        </div>
      )}

      {canWrite && impact && intervention.status !== "completed" && (
        <button onClick={handleMarkSuccessful} className="btn-primary text-sm">
          <CheckCircle2 className="w-3.5 h-3.5" />
          Mark Successful
        </button>
      )}
    </div>
  );
}
