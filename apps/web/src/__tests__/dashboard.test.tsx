import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import Dashboard from "../features/Dashboard";

vi.mock("../api", () => ({
  api: {
    dashboard: vi.fn(async () => ({
      entity: { id: "e1", name: "Acme Pvt Ltd", type: "pvt_ltd" },
      cap_table: { total_shares: 10000, total_invested: "280000.00", holders: 4 },
      fundraising: { rounds: 1, open_rounds: 1 },
      compliance: { total: 5, overdue: 2 },
      esop: { schemes: 1, options_granted: 4800 },
      governance: { meetings: 1, pending_resolutions: 0 },
      documents: 3,
      data_rooms: 1,
    })),
  },
}));

afterEach(cleanup);

describe("Dashboard", () => {
  it("renders aggregated stats from the API", async () => {
    render(<Dashboard entityId="e1" />);
    expect(await screen.findByText("Overview")).toBeTruthy();
    expect(screen.getByText("Shares issued")).toBeTruthy();
    expect(screen.getByText("280000.00")).toBeTruthy();
    // overdue stat present and non-zero
    expect(screen.getByText("Overdue")).toBeTruthy();
    expect(screen.getByText("2")).toBeTruthy();
    // no fund block for a company entity
    expect(screen.queryByText("Fund (AIF)")).toBeNull();
  });
});
