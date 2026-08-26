export type ProviderEvidence = {
  provider: string;
  sample_count: number;
  fill_probability: number;
  rejection_probability: number;
  expected_slippage_bps: number;
  expected_latency_ms: number;
  displayed_price_benefit_bps: number;
  rejection_asymmetry: number;
  model_version: string;
  generated_at: string;
};

export type EvidenceArtifact = {
  cohort_size: number;
  raw_records_shared: number;
  client_identities_shared: number;
  providers: ProviderEvidence[];
};

export type Contribution = {
  agent: string;
  summary: string;
};

export type ModelComparison = {
  pair: string;
  provider: string;
  federated_fill_prob: number;
  local_only_fill_prob: number;
  federated_logloss_held_out: number;
  local_only_logloss_held_out: number;
  model_agreement: boolean;
  federated_feature_importance: Record<string, number>;
};

export type PipelineResult = {
  order_context: {
    pair: string;
    side: string;
    size_bucket: string;
    volatility: string;
    available_providers: string[];
  };
  handoff_chain: string[];
  live_path: string;
  vanna_recommendation: {
    provider: string;
    expected_cost_bps: number;
    confidence: "low" | "medium" | "high";
    reason: string;
    model_version: string;
  };
  governance: {
    action: string;
    reasons: string[];
    automatic_execution: false;
    automatic_blacklist: false;
    collective_instruction: false;
    misconduct_finding: false;
  };
  contributions: Contribution[];
  model_comparison?: ModelComparison[] | { unavailable: string };
  last_look_signal?: {
    provider: string;
    rejection_asymmetry: number;
    level: string;
    review_required: boolean;
    explanation: string;
  };
  counterparty_risk?: {
    provider: string;
    reliability_score: number;
    route_posture: string;
    factors: string[];
  };
  margin?: {
    pressure: string;
    recommended_size_multiplier: number;
    human_review_required: boolean;
    factors: string[];
  };
  manipulation?: {
    provider: string;
    signal: string;
    anomaly_score: number;
    human_review_required: boolean;
  };
  privacy: {
    raw_records_shared: number;
    client_identities_shared: number;
  };
};
