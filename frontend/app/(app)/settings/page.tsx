"use client";

import { useEffect, useState } from "react";
import { Activity, Database, Server } from "lucide-react";

import { useAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import { formatDateTime, formatNumber } from "@/lib/format";

const ROLE_MATRIX: Array<{ role: string; read: boolean; incidents: boolean; interventions: boolean; experiments: boolean }> = [
  { role: "admin", read: true, incidents: true, interventions: true, experiments: true },
  { role: "pm", read: true, incidents: true, interventions: true, experiments: true },
  { role: "ops", read: true, incidents: true, interventions: true, experiments: false },
  { role: "engineer", read: true, incidents: true, interventions: true, experiments: false },
  { role: "support", read: true, incidents: false, interventions: false, experiments: false },
  { role: "viewer", read: true, incidents: false, interventions: false, experiments: false },
];

const OBSERVABILITY_ROLES = ["admin", "engineer", "ops"];

function Check({ value }: { value: boolean }) {
  return <span className={value ? "text-success" : "text-text-tertiary"}>{value ? "✓" : "—"}</span>;
}

interface ObservabilityResponse {
  api: {
    window_minutes: number;
    total_requests: number;
    error_rate_pct: number | null;
    avg_latency_ms: number | null;
    p95_latency_ms: number | null;
    by_feature: Array<{
      feature: string;
      requests: number;
      error_rate_pct: number;
      avg_latency_ms: number;
      p95_latency_ms: number;
    }>;
  };
  database: { total_queries_since_startup: number; avg_query_ms: number | null };
  pipeline_runs: Array<{
    run_id: string;
    completed_at: string | null;
    status: string;
    rows_processed: number | null;
  }>;
}

function ObservabilityPanel() {
  const [data, setData] = useState<ObservabilityResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<ObservabilityResponse>("/api/observability", { window_minutes: 60 })
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load observability data."));
  }, []);

  if (error) {
    return <div className="card px-4 py-3 text-sm text-critical">{error}</div>;
  }
  if (!data) {
    return <div className="card h-40 bg-bg-surface-raised animate-pulse" />;
  }

  return (
    <div className="card p-5 mb-6">
      <div className="flex items-center gap-2 mb-4">
        <Activity className="w-3.5 h-3.5 text-text-tertiary" />
        <div className="text-xs text-text-tertiary">
          OBSERVABILITY (last {data.api.window_minutes} min) — admin / engineer / ops only
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
        <div>
          <div className="text-xs text-text-secondary mb-1">Requests</div>
          <div className="text-lg font-semibold numeric text-text-primary">{formatNumber(data.api.total_requests)}</div>
        </div>
        <div>
          <div className="text-xs text-text-secondary mb-1">Error rate (5xx)</div>
          <div className={`text-lg font-semibold numeric ${(data.api.error_rate_pct ?? 0) > 0 ? "text-critical" : "text-success"}`}>
            {data.api.error_rate_pct ?? "—"}%
          </div>
        </div>
        <div>
          <div className="text-xs text-text-secondary mb-1">Avg latency</div>
          <div className="text-lg font-semibold numeric text-text-primary">{data.api.avg_latency_ms ?? "—"}ms</div>
        </div>
        <div>
          <div className="text-xs text-text-secondary mb-1">p95 latency</div>
          <div className="text-lg font-semibold numeric text-text-primary">{data.api.p95_latency_ms ?? "—"}ms</div>
        </div>
      </div>

      {data.api.by_feature.length > 0 && (
        <table className="w-full text-sm mb-5">
          <thead>
            <tr className="border-b border-border text-left text-xs text-text-tertiary">
              <th className="py-1.5 font-medium">Feature</th>
              <th className="py-1.5 font-medium text-right">Requests</th>
              <th className="py-1.5 font-medium text-right">Avg</th>
              <th className="py-1.5 font-medium text-right">p95</th>
              <th className="py-1.5 font-medium text-right">Errors</th>
            </tr>
          </thead>
          <tbody>
            {data.api.by_feature.map((f) => (
              <tr key={f.feature} className="border-b border-border/50">
                <td className="py-1.5 numeric">{f.feature}</td>
                <td className="py-1.5 text-right numeric">{f.requests}</td>
                <td className="py-1.5 text-right numeric text-text-secondary">{f.avg_latency_ms}ms</td>
                <td className="py-1.5 text-right numeric text-text-secondary">{f.p95_latency_ms}ms</td>
                <td className="py-1.5 text-right numeric">{f.error_rate_pct}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="flex items-center gap-6 pt-3 border-t border-border text-sm">
        <div className="flex items-center gap-1.5 text-text-secondary">
          <Database className="w-3.5 h-3.5" />
          DB: {formatNumber(data.database.total_queries_since_startup)} queries, avg{" "}
          {data.database.avg_query_ms ?? "—"}ms
        </div>
        <div className="flex items-center gap-1.5 text-text-secondary">
          <Server className="w-3.5 h-3.5" />
          Last pipeline run: {data.pipeline_runs[0] ? formatDateTime(data.pipeline_runs[0].completed_at) : "—"} (
          {data.pipeline_runs[0]?.status ?? "—"})
        </div>
      </div>
    </div>
  );
}

export default function SettingsPage() {
  const { user } = useAuth();

  return (
    <div className="p-6 max-w-[900px] mx-auto">
      <h1 className="text-xl font-semibold text-text-primary mb-6">Settings</h1>

      <div className="card p-5 mb-6">
        <div className="text-xs text-text-tertiary mb-3">YOUR ACCOUNT</div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="text-xs text-text-secondary mb-1">Name</div>
            <div className="text-sm text-text-primary">{user?.display_name}</div>
          </div>
          <div>
            <div className="text-xs text-text-secondary mb-1">Email</div>
            <div className="text-sm text-text-primary numeric">{user?.email}</div>
          </div>
          <div>
            <div className="text-xs text-text-secondary mb-1">Role</div>
            <div className="text-sm text-text-primary capitalize">{user?.role}</div>
          </div>
        </div>
      </div>

      {user && OBSERVABILITY_ROLES.includes(user.role) && <ObservabilityPanel />}

      <div className="card p-5 mb-6">
        <div className="text-xs text-text-tertiary mb-3">ROLE PERMISSIONS (RBAC)</div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs text-text-tertiary">
              <th className="py-2 font-medium">Role</th>
              <th className="py-2 font-medium text-center">Read Everything</th>
              <th className="py-2 font-medium text-center">Incidents</th>
              <th className="py-2 font-medium text-center">Interventions</th>
              <th className="py-2 font-medium text-center">Experiments</th>
            </tr>
          </thead>
          <tbody>
            {ROLE_MATRIX.map((row) => (
              <tr key={row.role} className={`border-b border-border/50 ${row.role === user?.role ? "bg-accent-bg/40" : ""}`}>
                <td className="py-2.5 capitalize">
                  {row.role}
                  {row.role === user?.role && <span className="ml-2 text-xs text-accent">(you)</span>}
                </td>
                <td className="py-2.5 text-center"><Check value={row.read} /></td>
                <td className="py-2.5 text-center"><Check value={row.incidents} /></td>
                <td className="py-2.5 text-center"><Check value={row.interventions} /></td>
                <td className="py-2.5 text-center"><Check value={row.experiments} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card px-4 py-3 text-xs text-text-tertiary">
        Audit logs record every incident and intervention change, attributed to the authenticated
        user who made it. This platform uses synthetic data only and does not process real payments.
      </div>
    </div>
  );
}

