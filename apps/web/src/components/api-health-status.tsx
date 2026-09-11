"use client";

import { useEffect, useState } from "react";

type ApiStatus = "checking" | "online" | "offline";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function ApiHealthStatus() {
  const [status, setStatus] = useState<ApiStatus>("checking");

  useEffect(() => {
    const controller = new AbortController();

    async function checkHealth() {
      try {
        const response = await fetch(`${API_URL}/health`, {
          headers: { Accept: "application/json" },
          signal: controller.signal,
        });
        const payload: unknown = await response.json();
        const isHealthy =
          response.ok &&
          typeof payload === "object" &&
          payload !== null &&
          "status" in payload &&
          payload.status === "ok";
        setStatus(isHealthy ? "online" : "offline");
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        setStatus("offline");
      }
    }

    void checkHealth();
    return () => controller.abort();
  }, []);

  const labels: Record<ApiStatus, string> = {
    checking: "Checking API connection…",
    online: "API connected",
    offline: "API unavailable",
  };

  return (
    <div className="flex items-center gap-3 text-sm font-medium" role="status" aria-live="polite">
      <span
        aria-hidden="true"
        className={`h-2.5 w-2.5 rounded-full ${
          status === "online"
            ? "bg-emerald-500"
            : status === "offline"
              ? "bg-rose-500"
              : "animate-pulse bg-amber-400"
        }`}
      />
      <span>{labels[status]}</span>
    </div>
  );
}

