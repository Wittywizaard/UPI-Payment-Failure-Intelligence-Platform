export type Role = "admin" | "pm" | "ops" | "engineer" | "support" | "viewer";

export interface CurrentUser {
  user_id: string;
  email: string;
  display_name: string;
  role: Role;
}

export interface DashboardResponse {
  window: { start: string; end: string; hours: number };
  kpis: {
    psr: number | null;
    psr_change_pp: number | null;
    total_transactions: number;
    failed_transactions: number;
    value_at_risk: number;
    retry_recovery_rate: number | null;
  };
  anomaly_detected: boolean;
  anomaly_severity: "P0" | "P1" | "P2" | null;
  data_freshness_note: string;
}

export interface DataFreshness {
  status: string;
  last_run: { run_id: string; completed_at: string; rows_processed: number } | null;
}

export interface FailureSegmentSummary {
  volume: number;
  success_count: number;
  failure_count: number;
  psr: number | null;
  failure_rate: number | null;
  avg_processing_time_ms: number | null;
  value_at_risk: number;
}

export interface TransactionRow {
  transaction_id: string;
  ts: string;
  payer_bank: string;
  payee_bank: string;
  psp: string;
  amount: number;
  status: "SUCCESS" | "FAILED" | "PENDING";
  error_code: string | null;
  device_type: string;
  os: string;
  app_version: string;
  network_type: string;
  transaction_type: string;
  geography: string;
  processing_time_ms: number;
}

export interface FailuresResponse {
  filters: Record<string, unknown>;
  segment_summary: FailureSegmentSummary;
  pagination: { page: number; page_size: number; total_rows: number; total_pages: number };
  transactions: TransactionRow[];
}

export interface FailuresFilters {
  start_date?: string;
  end_date?: string;
  payer_bank?: string;
  payee_bank?: string;
  psp?: string;
  error_code?: string;
  error_category?: string;
  device_type?: string;
  os?: string;
  app_version?: string;
  network_type?: string;
  transaction_type?: string;
  geography?: string;
  amount_min?: number;
  amount_max?: number;
  page?: number;
  page_size?: number;
}

export interface FingerprintResult {
  dimensions: Record<string, string>;
  label: string;
  volume: number;
  failed_count: number;
  observed_failure_rate_pct: number;
  baseline_failure_rate_pct: number;
  deviation_pp: number;
  contribution_pct: number;
  value_at_risk: number;
}

export interface RcaResponse {
  anomaly: boolean;
  severity: "P0" | "P1" | "P2" | null;
  observed_psr: number | null;
  baseline_psr: number | null;
  psr_drop_pp: number | null;
  affected_transactions: number;
  value_at_risk: number;
  window: { start: string; end: string };
  fingerprint: FingerprintResult | null;
  contributors: FingerprintResult[];
  evidence: Array<{
    dimension_combo: string;
    volume: number;
    failure_rate_pct: number;
    baseline_failure_rate_pct: number;
    deviation_pp: number;
    contribution_pct: number;
    value_at_risk: number;
  }>;
  ai_summary: string;
  recommended_actions: string[];
  disclaimer: string;
}

export type IncidentSeverity = "P0" | "P1" | "P2";
export type IncidentStatus = "open" | "investigating" | "mitigated" | "resolved" | "closed";

export interface Incident {
  incident_id: string;
  created_at: string;
  detected_at: string;
  severity: IncidentSeverity;
  title: string;
  status: IncidentStatus;
  owner: string | null;
  root_cause_summary: string | null;
  affected_bank: string | null;
  affected_error: string | null;
  affected_fingerprint: Record<string, string> | null;
  estimated_value_at_risk: number | null;
  affected_transactions: number | null;
  observed_psr: number | null;
  baseline_psr: number | null;
  resolved_at: string | null;
  updated_at: string;
}

export interface Intervention {
  intervention_id: string;
  incident_id: string;
  type: string;
  hypothesis: string;
  description: string | null;
  owner: string | null;
  start_time: string | null;
  end_time: string | null;
  expected_impact: string | null;
  actual_impact: {
    before: Record<string, number | null>;
    after: Record<string, number | null>;
    delta: Record<string, number | null>;
    guardrail_status: string;
  } | null;
  status: "proposed" | "active" | "completed" | "abandoned";
  outcome: string | null;
  created_at: string;
  updated_at: string;
}

export interface IncidentDetail extends Incident {
  interventions: Intervention[];
  timeline: Array<{ action: string; metadata_json: Record<string, unknown>; timestamp: string }>;
}

export interface Experiment {
  experiment_id: string;
  name: string;
  hypothesis: string;
  control_definition: string;
  variant_definition: string;
  primary_metric: string;
  secondary_metrics: string[] | null;
  guardrails: string[] | null;
  start_time: string | null;
  end_time: string | null;
  sample_size: number | null;
  result_summary: Record<string, unknown> | null;
  is_simulated: boolean;
  created_at: string;
}
