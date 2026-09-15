"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { XCircle } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { formatDateTime, formatInr, SEVERITY_COLORS, STATUS_COLORS } from "@/lib/format";
import type { Incident } from "@/lib/types";

const STATUS_OPTIONS = ["", "open", "investigating", "mitigated", "resolved", "closed"];
const SEVERITY_OPTIONS = ["", "P0", "P1", "P2"];

export default function IncidentsPage() {
  const [status, setStatus] = useState("");
  const [severity, setSeverity] = useState("");
  const [incidents, setIncidents] = useState<Incident[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.get<{ incidents: Incident[] }>("/api/incidents", {
        status: status || undefined,
        severity: severity || undefined,
      });
      setIncidents(resp.incidents);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load incidents.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, severity]);

  return (
    <div className="p-6 max-w-[1400px] mx-auto">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">Incidents</h1>
          <p className="text-sm text-text-secondary mt-0.5">
            Operational ownership and resolution of detected payment anomalies.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select value={severity} onChange={(e) => setSeverity(e.target.value)} className="input text-sm">
            {SEVERITY_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s || "All severities"}
              </option>
            ))}
          </select>
          <select value={status} onChange={(e) => setStatus(e.target.value)} className="input text-sm">
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s ? s[0].toUpperCase() + s.slice(1) : "All statuses"}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div className="card border-critical/40 bg-critical/5 px-4 py-3 mb-4 text-sm text-critical flex items-center gap-2">
          <XCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs text-text-tertiary">
              <th className="px-4 py-2.5 font-medium">Severity</th>
              <th className="px-4 py-2.5 font-medium">Title</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
              <th className="px-4 py-2.5 font-medium">Owner</th>
              <th className="px-4 py-2.5 font-medium text-right">Value at Risk</th>
              <th className="px-4 py-2.5 font-medium text-right">Detected</th>
            </tr>
          </thead>
          <tbody>
            {loading &&
              Array.from({ length: 4 }).map((_, i) => (
                <tr key={i} className="border-b border-border/50 animate-pulse">
                  <td colSpan={6} className="px-4 py-3">
                    <div className="h-3 bg-bg-surface-raised rounded w-full" />
                  </td>
                </tr>
              ))}
            {!loading && incidents?.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-text-tertiary text-sm">
                  No incidents match these filters. Create one from the RCA Workspace.
                </td>
              </tr>
            )}
            {!loading &&
              incidents?.map((incident) => (
                <tr key={incident.incident_id} className="border-b border-border/50 hover:bg-bg-surface-hover">
                  <td className="px-4 py-3">
                    <span className={`badge ${SEVERITY_COLORS[incident.severity]}`}>{incident.severity}</span>
                  </td>
                  <td className="px-4 py-3">
                    <Link href={`/incidents/${incident.incident_id}`} className="text-text-primary hover:text-accent">
                      {incident.title}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`badge ${STATUS_COLORS[incident.status]}`}>{incident.status}</span>
                  </td>
                  <td className="px-4 py-3 text-text-secondary">{incident.owner || "—"}</td>
                  <td className="px-4 py-3 text-right numeric">
                    {incident.estimated_value_at_risk ? formatInr(incident.estimated_value_at_risk) : "—"}
                  </td>
                  <td className="px-4 py-3 text-right numeric text-text-secondary">
                    {formatDateTime(incident.detected_at)}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
