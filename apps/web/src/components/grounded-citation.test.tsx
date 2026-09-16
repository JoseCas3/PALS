import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { GroundedCitation } from "./grounded-citation";

describe("GroundedCitation", () => {
  afterEach(cleanup);

  it.each([
    [3, 3, "Page 3"],
    [3, 5, "Pages 3–5"],
  ])("renders an accessible authoritative link for pages %s-%s", (start, end, pages) => {
    const view = render(
      <GroundedCitation
        citation={{
          alias: "S1",
          document_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
          chunk_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
          document_filename: "<source>.pdf",
          page_start: start,
          page_end: end,
        }}
      />,
    );

    const link = screen.getByRole("link", {
      name: `View source S1: <source>.pdf, ${pages} (opens in new tab)`,
    });
    expect(link).toHaveAttribute(
      "href",
      "/documents/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa?chunk=bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    );
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noreferrer");
    expect(screen.getByText("S1")).toBeInTheDocument();
    expect(screen.getByText("<source>.pdf")).toBeInTheDocument();
    expect(view.container.querySelector("source")).toBeNull();
  });
});
