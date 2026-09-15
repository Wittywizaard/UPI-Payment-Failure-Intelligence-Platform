"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Activity, AlertTriangle, ArrowRight, IndianRupee, RefreshCcw, TrendingDown, XCircle } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { formatInr, formatNumber, formatPct } from "@/lib/format";
import type { DashboardResponse } from "@/lib/types";
import KpiCard from "@/components/ui/KpiCard";

const HOUR_OPTIONS = [
  { label: "Last 24 hours", value: 24 },
  { label: "Last 48 hours", value: 48 },
  { label: "Last 7 days", value: 168 },
];

export default function OverviewPage() {
  const [hours, setHours] = useState(24);
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function load(h: number) {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.get<DashboardResponse>("/api/dashboard", { hours: h });
      setData(resp);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load dashboard data.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(hours);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hours]);

  return (
    <div className="p-6 max-w-[1400px] mx-auto">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">Payment Intelligence</h1>
          <p className="text-sm text-text-secondary mt-0.5">
            Monitor payment health, detect anomalies, and understand what is driving failures.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select value={hours} onChange={(e) => setHours(Number(e.target.value))} className="input text-sm">
            {HOUR_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <button onClick={() => load(hours)} className="btn-secondary text-sm">
            <RefreshCcw className="w-3.5 h-3.5" />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="card border-critical/40 bg-critical/5 px-4 py-3 mb-6 text-sm text-critical flex items-center gap-2">
          <XCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {loading && !data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 animate-pulse">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="card h-24 bg-bg-surface-raised" />
          ))}
        </div>
      )}

      {data && (
        <>
          {data.anomaly_detected && (
            <Link
              href="/rca"
              className="mb-6 flex items-center justify-between card border-critical/40 bg-critical/5 px-4 py-3 hover:border-critical/70 transition-colors group"
            >
              <div className="flex items-center gap-3">
                <AlertTriangle className="w-4 h-4 text-critical shrink-0" />
                <span className="text-sm text-text-primary">
                  Anomaly detected in this window
                  {data.anomaly_severity && (
                    <span className="ml-2 badge bg-critical/15 text-critical">{data.anomaly_severity}</span>
                  )}
                  — investigate the probable contributors in RCA.
                </span>
              </div>
              <ArrowRight className="w-4 h-4 text-critical shrink-0 group-hover:translate-x-0.5 transition-transform" />
            </Link>
          )}

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            <KpiCard
              label="Payment Success Rate"
              value={formatPct(data.kpis.psr)}
              change={data.kpis.psr_change_pp !== null ? `${Math.abs(data.kpis.psr_change_pp).toFixed(2)}pp` : null}
              changeDirection={data.kpis.psr_change_pp !== null ? (data.kpis.psr_change_pp >= 0 ? "up" : "down") : "neutral"}
              changeIsGood={(data.kpis.psr_change_pp ?? 0) >= 0}
              icon={Activity}
              tone={data.anomaly_detected ? "critical" : "default"}
            />
            <KpiCard label="Total Transactions" value={formatNumber(data.kpis.total_transactions)} icon={Activity} />
            <KpiCard
              label="Failed Transactions"
              value={formatNumber(data.kpis.failed_transactions)}
              icon={TrendingDown}
              tone={data.anomaly_detected ? "warning" : "default"}
            />
            <KpiCard label="Value at Risk" value={formatInr(data.kpis.value_at_risk)} icon={IndianRupee} tone="warning" />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-6">
            <div className="card p-4 md:col-span-2">
              <h3 className="text-sm font-medium text-text-primary mb-1">Recovery</h3>
              <p className="text-xs text-text-secondary mb-3">
                Share of eligible failures that were later retried and succeeded.
              </p>
              <span className="text-3xl font-semibold numeric text-success">
                {formatPct(data.kpis.retry_recovery_rate)}
              </span>
            </div>
            <div className="card p-4">
              <h3 className="text-sm font-medium text-text-primary mb-1">Data freshness</h3>
              <p className="text-xs text-text-secondary">{data.data_freshness_note}</p>
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            <Link href="/failures" className="btn-secondary text-sm">
              Open Failure Explorer
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
            <Link href="/rca" className="btn-secondary text-sm">
              Go to RCA Workspace
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </>
      )}
    </div>
  );
}
