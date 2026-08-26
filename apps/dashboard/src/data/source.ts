import type { EvidenceArtifact, PipelineResult } from "../types";

export type DashboardData = {
  evidence: EvidenceArtifact;
  result: PipelineResult;
};

export function expectedExecutionScore(provider: EvidenceArtifact["providers"][number]) {
  return (
    provider.fill_probability * provider.displayed_price_benefit_bps -
    provider.expected_slippage_bps -
    provider.rejection_probability * 1.5 -
    provider.expected_latency_ms / 100
  );
}

export function parseDashboardData(value: unknown): DashboardData {
  if (!value || typeof value !== "object") {
    throw new Error("The imported file must be a JSON object.");
  }

  const data = value as Partial<DashboardData>;
  if (!data.evidence?.providers?.length || !data.result?.vanna_recommendation) {
    throw new Error("Expected an object with evidence.providers and result.vanna_recommendation.");
  }
  return data as DashboardData;
}

export async function loadDashboardData(url: string): Promise<DashboardData> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Could not load dashboard data (${response.status}).`);
  }
  return parseDashboardData(await response.json());
}
