import { ApiHealthStatus } from "@/components/api-health-status";
import { DomainManager } from "@/components/domain-manager";

export default function Home() {
  return (
    <main className="mx-auto min-h-screen max-w-6xl px-6 py-12 sm:px-10">
      <header className="mb-10">
        <p className="mb-4 text-sm font-semibold uppercase tracking-[0.24em] text-[var(--accent)]">
          Personal Adaptive Learning System
        </p>
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div><h1 className="text-5xl font-semibold tracking-[-0.045em] sm:text-6xl">Academic setup</h1><p className="mt-3 text-lg text-[var(--muted)]">Manage the subjects, topics, and exams that shape your learning.</p></div>
          <ApiHealthStatus />
        </div>
      </header>
      <DomainManager />
    </main>
  );
}
