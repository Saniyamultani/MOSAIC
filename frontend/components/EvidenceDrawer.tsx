"use client";

import { useEffect, useState } from "react";
import { Alert, api, SEVERITY } from "@/lib/api";

interface EvidencePayload {
  alert: Alert;
  source: { name: string; url: string | null; trust_tier: number } | null;
  agent_trace: { agent: string; action: string; detail: string; at: string }[];
  run_outcome: string | null;
}

export default function EvidenceDrawer({
  alert,
  onClose,
}: {
  alert: Alert | null;
  onClose: () => void;
}) {
  const [data, setData] = useState<EvidencePayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    setError(null);
    if (!alert) return;
    api
      .evidence(alert.id)
      .then(setData)
      .catch((e) => setError(String(e)));
  }, [alert]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!alert) return null;
  const severity = SEVERITY[alert.severity] ?? SEVERITY.info;
  const chain = data?.alert.reasoning_chain ?? alert.reasoning_chain ?? [];
  const evidence = data?.alert.evidence ?? alert.evidence ?? [];
  const whyLines = (alert.why_it_matters || []).filter(
    (l) => l.trim() !== alert.explanation.trim()
  );

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div
        className="absolute inset-0 bg-ink/25 backdrop-blur-[2px]"
        onClick={onClose}
        aria-hidden
      />
      <aside className="relative flex h-full w-full max-w-[560px] flex-col overflow-y-auto border-l border-line bg-surface shadow-lift">
        <div className="sticky top-0 z-10 flex items-start gap-3 border-b border-line bg-surface/95 px-6 py-5 backdrop-blur">
          <div className="flex-1">
            <span className={`chip ${severity.chip}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${severity.dotColor}`} aria-hidden />
              {severity.label}
            </span>
            <h2 className="mt-2.5 font-serif text-[20px] leading-snug text-ink">
              {alert.headline}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg border border-line p-2 text-ink-faint hover:bg-paper"
            aria-label="Close"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2" fill="none">
              <path d="M18 6 6 18M6 6l12 12" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        <div className="space-y-7 px-6 py-6">
          {error && <p className="text-sm text-accent">{error}</p>}

          <section>
            <h3 className="label">Confidence</h3>
            <div className="mt-2 flex items-center gap-3">
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-line">
                <div
                  className={`h-full rounded-full ${
                    alert.severity === "critical" ? "bg-accent" : "bg-dusty-deep"
                  }`}
                  style={{ width: `${Math.round(alert.confidence * 100)}%` }}
                />
              </div>
              <span className="text-sm tabular-nums text-ink">
                {Math.round(alert.confidence * 100)}%
              </span>
            </div>
          </section>

          <section>
            <h3 className="label">Reasoning chain</h3>
            <ol className="mt-3 space-y-0">
              {chain.map((step, i) => (
                <li key={i} className="relative pl-6">
                  <span className="absolute left-0 top-1.5 h-2 w-2 rounded-full bg-dusty" />
                  {i < chain.length - 1 && (
                    <span className="absolute left-[3.5px] top-3.5 h-[calc(100%-6px)] w-px bg-line" />
                  )}
                  <div className="pb-4">
                    <div className="label">{step.step}</div>
                    <div className="text-sm text-ink">{step.label}</div>
                  </div>
                </li>
              ))}
            </ol>
          </section>

          {whyLines.length > 0 && (
            <section>
              <h3 className="label">Why we think this matters</h3>
              <ul className="mt-3 space-y-2">
                {whyLines.map((line, i) => (
                  <li key={i} className="flex gap-2.5 text-sm text-ink-soft">
                    <span
                      className={
                        line.startsWith("Caveat") ? "text-peach-deep" : "text-sage-deep"
                      }
                      aria-hidden
                    >
                      {line.startsWith("Caveat") ? "!" : "✓"}
                    </span>
                    <span>{line}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section>
            <h3 className="label">Evidence</h3>
            <div className="mt-3 space-y-2.5">
              {evidence.map((item, i) => (
                <div key={i} className="rounded-xl border border-line bg-paper px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span
                      className={`chip ${
                        item.kind === "external"
                          ? "border-dusty/40 bg-dusty-soft text-dusty-deep"
                          : "border-sage/40 bg-sage-soft text-sage-deep"
                      }`}
                    >
                      {item.kind === "external" ? "Outside world" : "Your records"}
                    </span>
                    {item.source && (
                      <span className="text-[11px] text-ink-faint">{item.source}</span>
                    )}
                  </div>
                  <p className="mt-2 text-sm font-medium text-ink">{item.title}</p>
                  {item.snippet && (
                    <p className="mt-1 line-clamp-3 text-[13px] leading-relaxed text-ink-soft">
                      {item.snippet}
                    </p>
                  )}
                  {item.url && (
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-2 inline-block text-[12px] text-dusty-deep underline underline-offset-2"
                    >
                      Open source
                    </a>
                  )}
                </div>
              ))}
              {evidence.length === 0 && (
                <p className="text-sm text-ink-faint">No documents attached.</p>
              )}
            </div>
          </section>

          {data?.agent_trace && data.agent_trace.length > 0 && (
            <section>
              <h3 className="label">Agent trace</h3>
              <ol className="mt-3 space-y-2">
                {data.agent_trace.map((step, i) => (
                  <li key={i} className="rounded-xl bg-paper px-4 py-2.5">
                    <div className="flex items-baseline gap-2">
                      <span className="text-[12px] font-medium text-ink">{step.agent}</span>
                      <span className="text-[11px] text-ink-faint">{step.action}</span>
                    </div>
                    <p className="mt-0.5 text-[13px] leading-relaxed text-ink-soft">
                      {step.detail}
                    </p>
                  </li>
                ))}
              </ol>
              {data.run_outcome && (
                <p className="mt-3 text-[12px] text-ink-faint">
                  Pipeline outcome: {data.run_outcome}
                </p>
              )}
            </section>
          )}
        </div>
      </aside>
    </div>
  );
}
