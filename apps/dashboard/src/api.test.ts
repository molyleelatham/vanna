import { afterEach, describe, expect, it, vi } from "vitest";
import { assessOrder, getDecisionStatus } from "./api";

const order = {
  pair: "EUR/USD",
  side: "BUY" as const,
  size_bucket: "1m-5m" as const,
  volatility: "high" as const,
  available_providers: ["LP_A", "LP_B", "LP_C"],
};

describe("SuperLink decision API", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("submits an asynchronous Flower job and reads its completion state", async () => {
    const fetch = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ job_id: "job-1", status: "queued" }), { status: 202 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ job_id: "job-1", status: "completed", result: {} }), { status: 200 }));
    vi.stubGlobal("fetch", fetch);

    await expect(assessOrder(order)).resolves.toMatchObject({ job_id: "job-1", status: "queued" });
    await expect(getDecisionStatus("job-1")).resolves.toMatchObject({ status: "completed" });

    expect(fetch.mock.calls[0][0]).toContain("/api/decision");
    expect(fetch.mock.calls[1][0]).toContain("/api/decisions/job-1");
  });
});
