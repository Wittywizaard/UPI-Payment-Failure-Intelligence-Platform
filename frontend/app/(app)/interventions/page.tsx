"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { XCircle } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { Intervention } from "@/lib/types";

export default function InterventionsPage() {
  const [interventions, setInterventions] = useState<Intervention[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<{ interventions: Intervention[] }>("/api/interventions")
      .then((resp) => setInterventions(resp.interventions))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load interventions."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6 max-w-[1200px] mx-auto">
      <div className="mb-4">
        <h1 className="text-xl font-semibold text-text-primary">Intervention Center</h1>
        <p className="text-sm text-text-secondary mt-0.5">Track actions taken against incidents and their measured outcomes.</p>
      </div>

      {error && (
        <div className="card border-critical/40 bg-critical/5 px-4 py-3 mb-4 text-sm text-critical flex items-center gap-2">
          <XCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {loading && <div className="card h-32 bg-bg-surface-raised animate-pulse" />}

      {!loading && interventions?.length === 0 && (
        <div className="card p-10 text-center text-sm text-text-tertiary">
          No interventions yet. Create one from an incident&apos;s RCA.
        </div>
      )}

      {!loading && interventions && interventions.length > 0 && (
        <div className="space-y-2">
          {interventions.map((iv) => (
            <Link
              key={iv.intervention_id}
              href={`/interventions/${iv.intervention_id}`}
              className="card p-4 flex items-center justify-between hover:border-accent/50 transition-colors"
            >
              <div>
                <div className="text-sm font-medium text-text-primary numeric">{iv.type}</div>
                <div className="text-xs text-text-secondary mt-0.5 max-w-lg truncate">{iv.hypothesis}</div>
              </div>
              <div className="flex items-center gap-3">
                {iv.actual_impact && (
                  <span
                    className={`badge ${
                      (iv.actual_impact.delta.psr_pp as number) >= 0 ? "bg-success/15 text-success" : "bg-critical/15 text-critical"
                    }`}
                  >
                    {(iv.actual_impact.delta.psr_pp as number) >= 0 ? "+" : ""}
                    {(iv.actual_impact.delta.psr_pp as number)?.toFixed(1)}pp PSR
                  </span>
                )}
                <span className="badge bg-bg-surface-raised text-text-secondary border border-border">{iv.status}</span>
                <span className="text-xs text-text-tertiary numeric">{formatDateTime(iv.created_at)}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
