import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Dashboard from "../features/Dashboard";

vi.mock("../api", () => ({
  api: {
    dashboard: vi.fn(async () => ({
      entity: { id: "e1", name: "Acme Pvt Ltd", type: "pvt_ltd" },
      cap_table: {
        total_shares: 10000,
        total_invested: "280000.00",
        holders: 4,
        by_class: [
          { name: "Equity", kind: "equity", quantity: 9000, pct: 90.0 },
          { name: "Series A CCPS", kind: "ccps", quantity: 1000, pct: 10.0 },
        ],
      },
      capital: {
        authorized_shares: 100000,
        issued: 10000,
        available: 90000,
        esop_pool: 5000,
        esop_granted: 4800,
      },
      valuation: {
        status: "active",
        fmv_per_share: "120.5000",
        method: "rule_11ua",
        valuation_date: "2026-07-01",
        valid_until: null,
        valuer_name: "RV & Co",
      },
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
    render(
      <MemoryRouter>
        <Dashboard entityId="e1" />
      </MemoryRouter>
    );
    expect(await screen.findByText("Ownership breakdown")).toBeTruthy();
    expect(screen.getAllByText("Shares issued").length).toBeGreaterThan(0);
    expect(screen.getByText("280000.00")).toBeTruthy();
    // donut legends show both security classes
    expect(screen.getByText("Equity")).toBeTruthy();
    expect(screen.getByText("Series A CCPS")).toBeTruthy();
    // authorized-capital panel
    expect(screen.getByText("Authorized shares")).toBeTruthy();
    expect(screen.getByText("Available to issue")).toBeTruthy();
    expect(screen.getByText("90,000")).toBeTruthy();
    // valuation status card
    // fmtMoney renders the per-share FMV with lakh/crore grouping, ≤2dp
    expect(screen.getByText("FMV ₹120.5 per share")).toBeTruthy();
    // overdue stat present and non-zero
    expect(screen.getByText("Overdue")).toBeTruthy();
    expect(screen.getByText("2")).toBeTruthy();
    // no fund block for a company entity
    expect(screen.queryByText("Fund (AIF)")).toBeNull();
  });
});
