import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiHealthStatus } from "./api-health-status";

describe("ApiHealthStatus", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("shows the API as connected after a successful health response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({ status: "ok" }),
      }),
    );

    render(<ApiHealthStatus />);

    expect(screen.getByRole("status")).toHaveTextContent("Checking API connection");
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("API connected"));
  });

  it("shows the API as unavailable when the request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network unavailable")));

    render(<ApiHealthStatus />);

    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("API unavailable"));
  });
});
