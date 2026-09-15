export function formatInr(amount: number): string {
  if (amount >= 10_000_000) return `₹${(amount / 10_000_000).toFixed(2)} Cr`;
  if (amount >= 100_000) return `₹${(amount / 100_000).toFixed(2)} L`;
  return `₹${amount.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

export function formatPct(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(digits)}%`;
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString("en-IN");
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  return ms < 1000 ? `${Math.round(ms)}ms` : `${(ms / 1000).toFixed(1)}s`;
}

export const SEVERITY_COLORS: Record<string, string> = {
  P0: "bg-critical/15 text-critical",
  P1: "bg-warning/15 text-warning",
  P2: "bg-accent/15 text-accent",
};

export const STATUS_COLORS: Record<string, string> = {
  open: "bg-critical/15 text-critical",
  investigating: "bg-warning/15 text-warning",
  mitigated: "bg-ai/15 text-ai",
  resolved: "bg-success/15 text-success",
  closed: "bg-text-tertiary/15 text-text-secondary",
};
