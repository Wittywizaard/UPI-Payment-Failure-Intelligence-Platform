"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { FlaskConical, XCircle } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import type { Experiment } from "@/lib/types";

export default function ExperimentsPage() {
  const [experiments, setExperiments] = useState<Experiment[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<{ experiments: Experiment[] }>("/api/experiments")
      .then((resp) => setExperiments(resp.experiments))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load experiments."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6 max-w-[1200px] mx-auto">
      <div className="mb-4">
        <h1 className="text-xl font-semibold text-text-primary">Experiments</h1>
        <p className="text-sm text-text-secondary mt-0.5">
          Product experiments measuring the impact of interventions. All results below are simulated/project data.
        </p>
      </div>

      {error && (
        <div className="card border-critical/40 bg-critical/5 px-4 py-3 mb-4 text-sm text-critical flex items-center gap-2">
          <XCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {loading && <div className="card h-32 bg-bg-surface-raised animate-pulse" />}

      {!loading && experiments?.length === 0 && (
        <div className="card p-10 text-center text-sm text-text-tertiary">No experiments recorded yet.</div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {experiments?.map((exp) => (
          <Link key={exp.experiment_id} href={`/experiments/${exp.experiment_id}`} className="card p-4 hover:border-accent/50 transition-colors">
            <div className="flex items-center gap-2 mb-2">
              <FlaskConical className="w-3.5 h-3.5 text-ai" />
              <span className="text-sm font-medium text-text-primary">{exp.name}</span>
              {exp.is_simulated && (
                <span className="badge bg-warning/15 text-warning ml-auto">SIMULATED</span>
              )}
            </div>
            <p className="text-xs text-text-secondary line-clamp-2">{exp.hypothesis}</p>
            <div className="mt-3 text-xs text-text-tertiary">
              Primary metric: <span className="numeric text-text-secondary">{exp.primary_metric}</span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
