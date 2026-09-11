import { ApiHealthStatus } from "@/components/api-health-status";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-5xl items-center px-6 py-16 sm:px-10">
      <section className="w-full rounded-[2rem] border border-[var(--border)] bg-[var(--surface)] p-8 shadow-[0_30px_100px_rgba(31,68,47,0.12)] backdrop-blur sm:p-14">
        <p className="mb-5 text-sm font-semibold uppercase tracking-[0.24em] text-[var(--accent)]">
          Personal Adaptive Learning System
        </p>
        <h1 className="max-w-3xl text-5xl font-semibold tracking-[-0.045em] sm:text-7xl">
          Learn with direction.
        </h1>
        <p className="mt-7 max-w-2xl text-lg leading-8 text-[var(--muted)] sm:text-xl">
          PALS will turn real practice into a clear picture of what you know and what to study
          next.
        </p>
        <div className="mt-12 border-t border-[var(--border)] pt-7">
          <ApiHealthStatus />
        </div>
      </section>
    </main>
  );
}

