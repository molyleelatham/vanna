import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "./App";

describe("Vanna dashboard", () => {
  it("renders a non-executable order ticket and safety controls", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "Execution terminal" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Assess order" })).toBeInTheDocument();
    expect(screen.getByText("Automatic execution disabled")).toBeInTheDocument();
    expect(screen.getByText("Broker execution")).toBeInTheDocument();
  });
});
