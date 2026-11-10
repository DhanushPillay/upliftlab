export interface AteResult {
  estimate: number;
  standard_error: number;
  ci_low: number;
  ci_high: number;
  p_value: number;
  n_treated: number;
  n_control: number;
  method: string;
}

export interface SrmResult {
  labels: string[];
  counts: number[];
  expected_counts: number[];
  chi_square: number | null;
  p_value: number;
  method: string;
  alpha: number;
  detected: boolean;
}

export interface CupedResult {
  theta: number;
  raw: AteResult;
  adjusted: AteResult;
  variance_reduction: number;
  correlation: number;
}

export interface Readout {
  dataset: string;
  dataset_sha256: string;
  rows: number;
  outcome: string;
  covariate: string;
  alpha: number;
  seed: number;
  bootstrap: number;
  srm: SrmResult;
  balance: Array<{
    covariate: string;
    treated_mean: number;
    control_mean: number;
    smd: number | null;
  }>;
  ate: AteResult;
  bootstrap_result: {
    estimate: number;
    ci_low: number;
    ci_high: number;
    n_bootstrap: number;
  };
  cuped: CupedResult;
  caveats: string[];
}

export interface CurvePoint {
  fraction: number;
  model: number;
  random: number;
}

export interface SegmentRow {
  segment: number;
  label: string;
  n: number;
  treated_share: number;
  predicted_uplift: number;
  observed_uplift: number | null;
  ci_low: number | null;
  ci_high: number | null;
}

export interface PolicyResult {
  name: string;
  budget_fraction: number;
  n_target: number;
  incremental_conversions: number;
  value: number;
  cost: number;
  profit: number;
  roi: number | null;
  ci_low: number | null;
  ci_high: number | null;
  n_bootstrap: number;
}

export interface UpliftReport {
  schema_version: number;
  dataset: string;
  dataset_sha256: string;
  outcome: string;
  seed: number;
  model_name: string;
  selected_candidate: string;
  split: Record<string, number>;
  holdout_ate: AteResult;
  metrics: {
    total_incremental: number;
    overall_uplift: number;
    auuc: number;
    random_auuc: number;
    qini: number | null;
    uplift_top_decile: number;
    top_decile_share: number | null;
  };
  curve: CurvePoint[];
  segments: SegmentRow[];
  policy: PolicyResult;
  baselines: PolicyResult[];
  caveats: string[];
}

export interface OverviewResponse {
  dataset: string;
  rows: number;
  sha256: string;
  readout: Readout;
  uplift: UpliftReport;
}

export interface OverviewRequest {
  dataset: string;
  outcome: string;
  seed: number;
  alpha: number;
  bootstrap: number;
  budget_fraction: number;
  value_per_conversion: number;
  cost_per_contact: number;
  policy_bootstrap: number;
}

export const defaultRequest: OverviewRequest = {
  dataset: "hillstrom",
  outcome: "visit",
  seed: 42,
  alpha: 0.05,
  bootstrap: 500,
  budget_fraction: 0.2,
  value_per_conversion: 2,
  cost_per_contact: 0.05,
  policy_bootstrap: 200,
};

export class ApiError extends Error {
  status: number;
  type: string;

  constructor(message: string, status: number, type: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.type = type;
  }
}

async function request<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    let detail = response.statusText;
    let type = "HTTPError";
    try {
      const payload = (await response.json()) as { detail?: string; type?: string };
      detail = payload.detail ?? detail;
      type = payload.type ?? type;
    } catch {
      // Keep the status text when the body is not JSON.
    }
    throw new ApiError(detail, response.status, type);
  }
  return (await response.json()) as T;
}

export function fetchOverview(body: OverviewRequest): Promise<OverviewResponse> {
  return request<OverviewResponse>("/api/overview", body);
}

export function fetchPolicy(
  body: Omit<OverviewRequest, "alpha" | "bootstrap">,
): Promise<{ policy: PolicyResult; baselines: PolicyResult[] }> {
  return request("/api/policy", body);
}
