"use client";

import { useEffect, useState } from "react";
import { Filter, RotateCcw, XCircle } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { formatDateTime, formatDuration, formatInr, formatNumber, formatPct } from "@/lib/format";
import type { FailuresFilters, FailuresResponse } from "@/lib/types";
import KpiCard from "@/components/ui/KpiCard";

const FILTER_FIELDS: Array<{ key: keyof FailuresFilters; label: string }> = [
  { key: "payer_bank", label: "Payer Bank" },
  { key: "psp", label: "PSP" },
  { key: "error_code", label: "Error Code" },
  { key: "device_type", label: "Device" },
  { key: "os", label: "OS" },
  { key: "app_version", label: "App Version" },
  { key: "network_type", label: "Network" },
];

const STATUS_BADGE: Record<string, string> = {
  SUCCESS: "bg-success/15 text-success",
  FAILED: "bg-critical/15 text-critical",
  PENDING: "bg-warning/15 text-warning",
};

const ANOMALY_PRESET: FailuresFilters = {
  payer_bank: "BANK_A",
  device_type: "Android",
  os: "U28",
  app_version: "4.2.1",
  start_date: "2026-08-29T18:00:00",
  end_date: "2026-08-29T20:00:00",
};

export default function FailureExplorerPage() {
  const [filters, setFilters] = useState<FailuresFilters>({ page: 1, page_size: 25 });
  const [data, setData] = useState<FailuresResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function load(f: FailuresFilters) {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.get<FailuresResponse>("/api/failures", f as Record<string, string | number>);
      setData(resp);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load failure data.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(filters);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  function updateFilter(key: keyof FailuresFilters, value: string) {
    setFilters((prev) => ({ ...prev, [key]: value || undefined, page: 1 }));
  }

  function resetFilters() {
    setFilters({ page: 1, page_size: 25 });
  }

  function applyAnomalyPreset() {
    setFilters({ ...ANOMALY_PRESET, page: 1, page_size: 25 });
  }

  return (
    <div className="p-6 max-w-[1400px] mx-auto">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">Failure Explorer</h1>
          <p className="text-sm text-text-secondary mt-0.5">
            Filter by any dimension, drill down, and inspect individual transactions.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={applyAnomalyPreset} className="btn-secondary text-sm">
            Load known anomaly
          </button>
          <button onClick={resetFilters} className="btn-ghost text-sm">
            <RotateCcw className="w-3.5 h-3.5" />
            Reset
          </button>
        </div>
      </div>

      <div className="card p-4 mb-4">
        <div className="flex items-center gap-2 mb-3 text-xs text-text-secondary">
          <Filter className="w-3.5 h-3.5" />
          Filters
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2">
          {FILTER_FIELDS.map((field) => (
            <input
              key={field.key}
              placeholder={field.label}
              value={(filters[field.key] as string) || ""}
              onChange={(e) => updateFilter(field.key, e.target.value)}
              className="input text-sm"
            />
          ))}
        </div>
        <div className="grid grid-cols-2 gap-2 mt-2">
          <input
            type="datetime-local"
            value={filters.start_date || ""}
            onChange={(e) => updateFilter("start_date", e.target.value)}
            className="input text-sm"
          />
          <input
            type="datetime-local"
            value={filters.end_date || ""}
            onChange={(e) => updateFilter("end_date", e.target.value)}
            className="input text-sm"
          />
        </div>
      </div>

      {error && (
        <div className="card border-critical/40 bg-critical/5 px-4 py-3 mb-4 text-sm text-critical flex items-center gap-2">
          <XCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
            <KpiCard label="Volume" value={formatNumber(data.segment_summary.volume)} />
            <KpiCard
              label="PSR"
              value={formatPct(data.segment_summary.psr)}
              tone={data.segment_summary.failure_rate && data.segment_summary.failure_rate > 15 ? "critical" : "default"}
            />
            <KpiCard label="Failure Rate" value={formatPct(data.segment_summary.failure_rate)} />
            <KpiCard label="Avg Processing Time" value={formatDuration(data.segment_summary.avg_processing_time_ms)} />
            <KpiCard label="Value at Risk" value={formatInr(data.segment_summary.value_at_risk)} tone="warning" />
          </div>

          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-text-tertiary">
                    <th className="px-3 py-2.5 font-medium">Time</th>
                    <th className="px-3 py-2.5 font-medium">Bank</th>
                    <th className="px-3 py-2.5 font-medium">PSP</th>
                    <th className="px-3 py-2.5 font-medium">Error</th>
                    <th className="px-3 py-2.5 font-medium">Device</th>
                    <th className="px-3 py-2.5 font-medium">App</th>
                    <th className="px-3 py-2.5 font-medium text-right">Amount</th>
                    <th className="px-3 py-2.5 font-medium text-right">Proc. Time</th>
                    <th className="px-3 py-2.5 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {loading &&
                    Array.from({ length: 8 }).map((_, i) => (
                      <tr key={i} className="border-b border-border/50 animate-pulse">
                        <td colSpan={9} className="px-3 py-3">
                          <div className="h-3 bg-bg-surface-raised rounded w-full" />
                        </td>
                      </tr>
                    ))}
                  {!loading && data.transactions.length === 0 && (
                    <tr>
                      <td colSpan={9} className="px-3 py-10 text-center text-text-tertiary text-sm">
                        No transactions match these filters.
                      </td>
                    </tr>
                  )}
                  {!loading &&
                    data.transactions.map((txn) => (
                      <tr key={txn.transaction_id} className="border-b border-border/50 hover:bg-bg-surface-hover">
                        <td className="px-3 py-2.5 numeric text-text-secondary">{formatDateTime(txn.ts)}</td>
                        <td className="px-3 py-2.5">{txn.payer_bank}</td>
                        <td className="px-3 py-2.5 text-text-secondary">{txn.psp}</td>
                        <td className="px-3 py-2.5 text-text-secondary">{txn.error_code || "—"}</td>
                        <td className="px-3 py-2.5 text-text-secondary">
                          {txn.device_type} / {txn.os}
                        </td>
                        <td className="px-3 py-2.5 text-text-secondary numeric">{txn.app_version}</td>
                        <td className="px-3 py-2.5 text-right numeric">{formatInr(txn.amount)}</td>
                        <td className="px-3 py-2.5 text-right numeric text-text-secondary">
                          {formatDuration(txn.processing_time_ms)}
                        </td>
                        <td className="px-3 py-2.5">
                          <span className={`badge ${STATUS_BADGE[txn.status]}`}>{txn.status}</span>
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>

            {data.pagination.total_pages > 1 && (
              <div className="flex items-center justify-between px-3 py-2.5 border-t border-border text-xs text-text-secondary">
                <span>
                  Page {data.pagination.page} of {data.pagination.total_pages} ({formatNumber(data.pagination.total_rows)}{" "}
                  rows)
                </span>
                <div className="flex gap-1.5">
                  <button
                    disabled={data.pagination.page <= 1}
                    onClick={() => setFilters((prev) => ({ ...prev, page: (prev.page || 1) - 1 }))}
                    className="btn-ghost px-2 py-1 text-xs"
                  >
                    Previous
                  </button>
                  <button
                    disabled={data.pagination.page >= data.pagination.total_pages}
                    onClick={() => setFilters((prev) => ({ ...prev, page: (prev.page || 1) + 1 }))}
                    className="btn-ghost px-2 py-1 text-xs"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
