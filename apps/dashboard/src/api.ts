import type { PipelineResult } from "./types";

const gatewayOrigin = import.meta.env.VITE_GATEWAY_ORIGIN ?? "http://127.0.0.1:8010";

export type Quote = {
  pair: string;
  bid: number;
  ask: number;
  timestamp: string;
  source: "alpha-vantage" | "local-demo-fallback";
  fallback: boolean;
};

export type DecisionJob = {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  result?: PipelineResult;
  decision_digest?: string;
  error?: string;
};

export type Connectivity = {
  gateway: "reachable";
  superlink: "reachable" | "unreachable";
  superlink_endpoint: string;
  agentapp_mode: string;
  data_boundary: string;
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${gatewayOrigin}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  const body = await response.json() as T & { error?: string };
  if (!response.ok) throw new Error(body.error ?? "The local gateway is unavailable.");
  return body;
}

export function getQuote(pair: string) {
  return request<Quote>(`/api/quote?pair=${encodeURIComponent(pair)}`);
}

export function getConnectivity() {
  return request<Connectivity>("/api/connectivity");
}

export function assessOrder(order: PipelineResult["order_context"]) {
  return request<DecisionJob>("/api/decision", {
    method: "POST",
    body: JSON.stringify(order),
  });
}

export function getDecisionStatus(jobId: string) {
  return request<DecisionJob>(`/api/decisions/${encodeURIComponent(jobId)}`);
}

export function queueApproval(jobId: string) {
  return request<{ status: string }>("/api/approval-queue", {
    method: "POST",
    body: JSON.stringify({
      job_id: jobId,
      operator_acknowledged: true,
    }),
  });
}
