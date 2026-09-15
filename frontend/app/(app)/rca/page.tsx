"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, Info, Sparkles, XCircle } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { useAuth, CAN_WRITE_ROLES } from "@/lib/auth-context";
import { formatInr, formatNumber, formatPct, SEVERITY_COLORS } from "@/lib/format";
import type { Incident, Intervention, RcaResponse } from "@/lib/types";

const DEFAULT_START = "2026-08-29T18:00";
const DEFAULT_END = "2026-08-29T20:00";

export default function RcaWorkspacePage() {
  const { user } = useAuth();
  const router = useRouter();
  const [start, setStart] = useState(DEFAULT_START);
  const [end, setEnd] = useState(DEFAULT_END);
  const [rca, setRca] = useState<RcaResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [creatingIncident, setCreatingIncident] = useState(false);
  const [incident, setIncident] = useState<Incident | null>(null);
  const [creatingIntervention, setCreatingIntervention] = useState(false);
  const [intervention, setIntervention] = useState<Intervention | null>(null);
  const [hypothesis, setHypothesis] = useState(
    "Prompting affected users to retry via an alternate PSP will recover a portion of failed payments."
  );
  const [actionError, setActionError] = useState<string | null>(null);

  const canWrite = user ? CAN_WRITE_ROLES.includes(user.role) : false;

  async function loadRca() {
    setLoading(true);
    setError(null);
    setIncident(null);
    setIntervention(null);
    try {
      const resp = await api.get<RcaResponse>("/api/rca/ad-hoc", {
        start: `${start}:00`,
        end: `${end}:00`,
      });
      setRca(resp);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to run RCA.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadRca();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleCreateIncident() {
    if (!rca) return;
    setActionError(null);
    setCreatingIncident(true);
    try {
      const created = await api.post<Incident>("/api/incidents", {
        title: `${rca.severity} - Payment Success Rate Drop${rca.fingerprint ? ` (${rca.fingerprint.label})` : ""}`,
        severity: rca.severity,
        detected_at: `${start}:00`,
        affected_fingerprint: rca.fingerprint?.dimensions ?? null,
        estimated_value_at_risk: rca.value_at_risk,
        affected_transactions: rca.affected_transactions,
        observed_psr: rca.observed_psr,
        baseline_psr: rca.baseline_psr,
      });
      setIncident(created);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Failed to create incident.");
    } finally {
      setCreatingIncident(false);
    }
  }

  async function handleCreateIntervention() {
    if (!incident) return;
    setActionError(null);
    setCreatingIntervention(true);
    try {
      const created = await api.post<Intervention>("/api/interventions", {
        incident_id: incident.incident_id,
        type: "contextual_recovery_prompt",
        hypothesis,
        start_time: `${end}:00`,
      });
      setIntervention(created);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Failed to create intervention.");
    } finally {
      setCreatingIntervention(false);
    }
  }

  return (
    <div className="p-6 max-w-[1400px] mx-auto">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">RCA Workspace</h1>
          <p className="text-sm text-text-secondary mt-0.5">
            Evidence-backed diagnosis: observed vs. expected PSR, probable contributors, and recommended actions.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} className="input text-sm" />
          <span className="text-text-tertiary text-sm">to</span>
          <input type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} className="input text-sm" />
          <button onClick={loadRca} className="btn-secondary text-sm">
            Run RCA
          </button>
        </div>
      </div>

      {error && (
        <div className="card border-critical/40 bg-critical/5 px-4 py-3 mb-4 text-sm text-critical flex items-center gap-2">
          <XCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {loading && <div className="card h-64 bg-bg-surface-raised animate-pulse" />}

      {!loading && rca && !rca.anomaly && (
        <div className="card p-6 text-center">
          <Info className="w-5 h-5 text-text-tertiary mx-auto mb-2" />
          <p className="text-sm text-text-secondary">
            No significant PSR anomaly detected for this window (observed {formatPct(rca.observed_psr)} vs. baseline{" "}
            {formatPct(rca.baseline_psr)}).
          </p>
          <p className="text-xs text-text-tertiary mt-2">
            Try the default injected-anomaly window: 2026-08-29 18:00–20:00.
          </p>
        </div>
      )}

      {!loading && rca && rca.anomaly && (
        <div className="space-y-4">
          <div className="card p-5 border-critical/30">
            <div className="flex items-center gap-2 mb-3">
              <AlertTriangle className="w-4 h-4 text-critical" />
              <span className={`badge ${SEVERITY_COLORS[rca.severity || "P2"]}`}>{rca.severity}</span>
              <span className="text-sm font-medium text-text-primary">Payment Success Rate Drop</span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-xs text-text-tertiary mb-1">Observed PSR</div>
                <div className="text-xl font-semibold numeric text-critical">{formatPct(rca.observed_psr)}</div>
              </div>
              <div>
                <div className="text-xs text-text-tertiary mb-1">Baseline PSR</div>
                <div className="text-xl font-semibold numeric text-text-primary">{formatPct(rca.baseline_psr)}</div>
              </div>
              <div>
                <div className="text-xs text-text-tertiary mb-1">Affected Transactions</div>
                <div className="text-xl font-semibold numeric text-text-primary">
                  {formatNumber(rca.affected_transactions)}
                </div>
              </div>
              <div>
                <div className="text-xs text-text-tertiary mb-1">Value at Risk</div>
                <div className="text-xl font-semibold numeric text-warning">{formatInr(rca.value_at_risk)}</div>
              </div>
            </div>
          </div>

          {rca.fingerprint && (
            <div className="card p-5">
              <div className="text-xs text-text-tertiary mb-2">FAILURE FINGERPRINT</div>
              <div className="text-lg font-semibold text-text-primary numeric mb-4">{rca.fingerprint.label}</div>

              <div className="text-xs text-text-tertiary mb-2">CONTRIBUTION TO FAILURE SPIKE</div>
              <div className="space-y-2">
                {rca.contributors.slice(0, 6).map((c) => (
                  <div key={c.label} className="flex items-center gap-3">
                    <div className="w-40 shrink-0 text-xs text-text-secondary truncate" title={c.label}>
                      {c.label}
                    </div>
                    <div className="flex-1 h-2 bg-bg-surface-raised rounded-full overflow-hidden">
                      <div
                        className="h-full bg-accent rounded-full"
                        style={{ width: `${Math.min(c.contribution_pct, 100)}%` }}
                      />
                    </div>
                    <div className="w-12 text-right text-xs numeric text-text-secondary">
                      {c.contribution_pct.toFixed(0)}%
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="card overflow-hidden">
            <div className="px-5 pt-4 pb-2 text-xs text-text-tertiary">EVIDENCE</div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-text-tertiary">
                    <th className="px-5 py-2 font-medium">Dimension</th>
                    <th className="px-3 py-2 font-medium text-right">Volume</th>
                    <th className="px-3 py-2 font-medium text-right">Failure Rate</th>
                    <th className="px-3 py-2 font-medium text-right">Baseline</th>
                    <th className="px-3 py-2 font-medium text-right">Delta</th>
                    <th className="px-3 py-2 font-medium text-right">Contribution</th>
                    <th className="px-5 py-2 font-medium text-right">Value at Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {rca.evidence.map((row) => (
                    <tr key={row.dimension_combo} className="border-b border-border/50">
                      <td className="px-5 py-2.5 numeric">{row.dimension_combo}</td>
                      <td className="px-3 py-2.5 text-right numeric">{formatNumber(row.volume)}</td>
                      <td className="px-3 py-2.5 text-right numeric text-critical">{row.failure_rate_pct.toFixed(1)}%</td>
                      <td className="px-3 py-2.5 text-right numeric text-text-secondary">
                        {row.baseline_failure_rate_pct.toFixed(1)}%
                      </td>
                      <td className="px-3 py-2.5 text-right numeric text-warning">+{row.deviation_pp.toFixed(1)}pp</td>
                      <td className="px-3 py-2.5 text-right numeric">{row.contribution_pct.toFixed(0)}%</td>
                      <td className="px-5 py-2.5 text-right numeric">{formatInr(row.value_at_risk)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="card p-5 border-ai/30 bg-ai-bg/40">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="w-4 h-4 text-ai" />
              <span className="text-xs font-medium text-ai">AI INVESTIGATION SUMMARY</span>
            </div>
            <p className="text-sm text-text-primary leading-relaxed">{rca.ai_summary}</p>
            <p className="text-xs text-text-tertiary mt-3 italic">{rca.disclaimer}</p>
          </div>

          <div className="card p-5">
            <div className="text-xs text-text-tertiary mb-3">RECOMMENDED ACTIONS</div>
            <ul className="space-y-2">
              {rca.recommended_actions.map((action, i) => (
                <li key={i} className="text-sm text-text-secondary flex items-start gap-2">
                  <span className="text-accent mt-0.5">•</span>
                  {action}
                </li>
              ))}
            </ul>
          </div>

          {actionError && (
            <div className="card border-critical/40 bg-critical/5 px-4 py-3 text-sm text-critical flex items-center gap-2">
              <XCircle className="w-4 h-4 shrink-0" />
              {actionError}
            </div>
          )}

          {!canWrite && (
            <div className="card px-4 py-3 text-sm text-text-tertiary flex items-center gap-2">
              <Info className="w-4 h-4 shrink-0" />
              Your role ({user?.role}) can view this RCA but cannot create incidents or interventions.
            </div>
          )}

          {canWrite && !incident && (
            <button onClick={handleCreateIncident} disabled={creatingIncident} className="btn-primary">
              {creatingIncident ? "Creating..." : "Create Incident"}
            </button>
          )}

          {incident && (
            <div className="card p-5 border-accent/30">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <div className="text-xs text-text-tertiary">INCIDENT CREATED</div>
                  <div className="text-sm font-medium text-text-primary">{incident.title}</div>
                </div>
                <button onClick={() => router.push(`/incidents/${incident.incident_id}`)} className="btn-secondary text-sm">
                  View Incident
                </button>
              </div>

              {!intervention && (
                <div className="pt-3 border-t border-border">
                  <label className="block text-xs text-text-secondary mb-1.5">Intervention hypothesis</label>
                  <textarea
                    value={hypothesis}
                    onChange={(e) => setHypothesis(e.target.value)}
                    rows={2}
                    className="input w-full mb-3 text-sm"
                  />
                  <button onClick={handleCreateIntervention} disabled={creatingIntervention} className="btn-primary text-sm">
                    {creatingIntervention ? "Creating..." : "Create Intervention"}
                  </button>
                </div>
              )}

              {intervention && (
                <div className="pt-3 border-t border-border flex items-center justify-between">
                  <div className="text-sm text-text-secondary">
                    Intervention <span className="numeric text-text-primary">{intervention.type}</span> created.
                  </div>
                  <button
                    onClick={() => router.push(`/interventions/${intervention.intervention_id}`)}
                    className="btn-secondary text-sm"
                  >
                    Measure Impact
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
