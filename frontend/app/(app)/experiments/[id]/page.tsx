"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, XCircle } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import type { Experiment } from "@/lib/types";

export default function ExperimentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [experiment, setExperiment] = useState<Experiment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<Experiment>(`/api/experiments/${id}`)
      .then(setExperiment)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load experiment."))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="p-6 max-w-[900px] mx-auto"><div className="card h-48 bg-bg-surface-raised animate-pulse" /></div>;
  if (!experiment) {
    return (
      <div className="p-6 max-w-[900px] mx-auto">
        <div className="card border-critical/40 bg-critical/5 px-4 py-3 text-sm text-critical flex items-center gap-2">
          <XCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      </div>
    );
  }

  const results = experiment.result_summary as Record<string, string | number> | null;

  return (
    <div className="p-6 max-w-[900px] mx-auto">
      <button onClick={() => router.push("/experiments")} className="btn-ghost text-sm mb-4">
        <ArrowLeft className="w-3.5 h-3.5" />
        Back to Experiments
      </button>

      <div className="card p-5 mb-4">
        <div className="flex items-center gap-2 mb-2">
          {experiment.is_simulated && <span className="badge bg-warning/15 text-warning">SIMULATED / PORTFOLIO DATA</span>}
        </div>
        <h1 className="text-lg font-semibold text-text-primary mb-3">{experiment.name}</h1>
        <p className="text-sm text-text-secondary leading-relaxed mb-4">{experiment.hypothesis}</p>

        <div className="grid grid-cols-2 gap-4 pt-4 border-t border-border">
          <div>
            <div className="text-xs text-text-tertiary mb-1">Control</div>
            <div className="text-sm text-text-secondary">{experiment.control_definition}</div>
          </div>
          <div>
            <div className="text-xs text-text-tertiary mb-1">Variant</div>
            <div className="text-sm text-text-secondary">{experiment.variant_definition}</div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 mt-4 pt-4 border-t border-border">
          <div>
            <div className="text-xs text-text-tertiary mb-1">Primary Metric</div>
            <div className="text-sm numeric text-text-primary">{experiment.primary_metric}</div>
          </div>
          {experiment.guardrails && (
            <div>
              <div className="text-xs text-text-tertiary mb-1">Guardrails</div>
              <div className="text-sm numeric text-text-primary">{experiment.guardrails.join(", ")}</div>
            </div>
          )}
        </div>
      </div>

      {results && (
        <div className="card p-5">
          <div className="text-xs text-text-tertiary mb-4">RESULTS</div>
          <div className="grid grid-cols-2 gap-6 mb-4">
            <div>
              <div className="text-xs text-text-secondary mb-1">Control</div>
              <div className="text-2xl font-semibold numeric text-text-primary">
                {results.recovery_rate_control_pct as number}%
              </div>
              <div className="text-xs text-text-tertiary">Recovery Rate</div>
            </div>
            <div>
              <div className="text-xs text-text-secondary mb-1">Variant</div>
              <div className="text-2xl font-semibold numeric text-success">
                {results.recovery_rate_variant_pct as number}%
              </div>
              <div className="text-xs text-text-tertiary">Recovery Rate</div>
            </div>
          </div>
          <p className="text-sm text-text-secondary pt-4 border-t border-border">{results.conclusion as string}</p>
        </div>
      )}
    </div>
  );
}
