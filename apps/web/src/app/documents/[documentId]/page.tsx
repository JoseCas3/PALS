import Link from "next/link";

import { DocumentDetail } from "@/components/document-detail";

export default async function DocumentPage({
  params,
  searchParams,
}: {
  params: Promise<{ documentId: string }>;
  searchParams: Promise<{ chunk?: string | string[] }>;
}) {
  const [{ documentId }, query] = await Promise.all([params, searchParams]);
  const chunkId = query.chunk === undefined
    ? null
    : typeof query.chunk === "string" ? query.chunk : "";

  return (
    <main className="mx-auto min-h-screen max-w-4xl px-6 py-12 sm:px-10">
      <Link className="back-link" href="/">← Back to study workspace</Link>
      <DocumentDetail documentId={documentId} chunkId={chunkId} />
    </main>
  );
}
