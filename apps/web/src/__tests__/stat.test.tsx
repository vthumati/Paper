import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import Stat from "../components/Stat";

afterEach(cleanup);

describe("Stat", () => {
  it("renders label and value", () => {
    render(<Stat label="Runway (months)" value={5} />);
    expect(screen.getByText("Runway (months)")).toBeTruthy();
    expect(screen.getByText("5")).toBeTruthy();
  });

  it("uses the warning colour when alerted", () => {
    render(<Stat label="Overdue" value={3} alert />);
    const value = screen.getByText("3");
    expect(value.style.color).toBe("var(--warn)");
  });
});
