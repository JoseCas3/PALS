import Link from "next/link";

import type { GroundedCitation as GroundedCitationValue } from "../lib/types";

export function GroundedCitation({ citation }: { citation: GroundedCitationValue }) {
  const pages = formatPageRange(citation.page_start, citation.page_end);
  const href = `/documents/${encodeURIComponent(citation.document_id)}?chunk=${encodeURIComponent(citation.chunk_id)}`;

  return (
    <article className="citation-card">
      <div>
        <strong className="citation-alias">{citation.alias}</strong>
        <span className="citation-filename">{citation.document_filename}</span>
        <span className="citation-pages">{pages}</span>
      </div>
      <Link
        className="citation-link"
        href={href}
        target="_blank"
        rel="noreferrer"
        aria-label={`View source ${citation.alias}: ${citation.document_filename}, ${pages} (opens in new tab)`}
      >
        View source
      </Link>
    </article>
  );
}

export function formatPageRange(pageStart: number, pageEnd: number): string {
  return pageStart === pageEnd ? `Page ${pageStart}` : `Pages ${pageStart}–${pageEnd}`;
}
