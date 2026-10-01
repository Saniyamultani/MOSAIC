"use client";

import { Alert, SEVERITY } from "@/lib/api";

export default function AlertCard({
  alert,
  onEvidence,
  onDismiss,
  compact = false,
}: {
  alert: Alert;
  onEvidence?: (alert: Alert) => void;
  onDismiss?: (alert: Alert) => void;
  compact?: boolean;
}) {
  const severity = SEVERITY[alert.severity] ?? SEVERITY.info;
  const critical = alert.severity === "critical";
  // A connection alert's checklist repeats its explanation; don't say it twice.
  const whyLines = (alert.why_it_matters || []).filter((l) => l.trim() !== alert.explanation.trim());

  return (
    <article
      className={`card p-5 transition-shadow hover:shadow-lift ${
        critical ? "border-accent/30" : ""
      }`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className={`chip ${severity.chip}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${severity.dotColor}`} aria-hidden />
          {severity.label}
        </span>
        {alert.entity && (
          <span className="text-[11px] text-ink-faint">on {alert.entity.name}</span>
        )}
        <span className="ml-auto text-[11px] tabular-nums text-ink-faint">
          {Math.round(alert.confidence * 100)}% confidence
        </span>
      </div>

      <h3
        className={`mt-3 font-serif leading-snug text-ink ${
          compact ? "text-[17px]" : "text-[19px]"
        }`}
      >
        {alert.headline}
      </h3>
      <p className="mt-2 text-sm leading-relaxed text-ink-soft">{alert.explanation}</p>

      {!compact && whyLines.length > 0 && (
        <ul className="mt-4 space-y-1.5 border-l-2 border-line pl-3.5">
          {whyLines.slice(0, 4).map((line, i) => (
            <li key={i} className="flex gap-2 text-[13px] text-ink-soft">
              <span
                className={`font-semibold ${
                  line.startsWith("Caveat") ? "text-peach-deep" : "text-sage-deep"
                }`}
                aria-hidden
              >
                {line.startsWith("Caveat") ? "!" : "•"}
              </span>
              <span>{line}</span>
            </li>
          ))}
        </ul>
      )}

      {!compact && alert.suggested_action && (
        <p className="mt-4 rounded-xl bg-paper px-3.5 py-2.5 text-[13px] text-ink-soft">
          <span className="label mr-2">Suggested</span>
          {alert.suggested_action}
        </p>
      )}

      <div className="mt-4 flex items-center gap-2">
        {onEvidence && (
          <button className="btn-primary" onClick={() => onEvidence(alert)}>
            Why am I seeing this?
          </button>
        )}
        {onDismiss && alert.status === "new" && (
          <button className="btn-ghost" onClick={() => onDismiss(alert)}>
            Dismiss
          </button>
        )}
        {alert.status === "dismissed" && (
          <span className="text-[11px] text-ink-faint">Dismissed</span>
        )}
      </div>
    </article>
  );
}
