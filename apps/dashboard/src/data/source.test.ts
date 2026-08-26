import { describe, expect, it } from "vitest";
import { demoEvidence, demoResult } from "./demo";
import { parseDashboardData } from "./source";

describe("parseDashboardData", () => {
  it("accepts a dashboard snapshot with evidence and pipeline result", () => {
    expect(parseDashboardData({ evidence: demoEvidence, result: demoResult }).result.vanna_recommendation.provider).toBe("LP_B");
  });

  it("rejects incomplete imports", () => {
    expect(() => parseDashboardData({ evidence: demoEvidence })).toThrow("Expected an object");
  });
});
