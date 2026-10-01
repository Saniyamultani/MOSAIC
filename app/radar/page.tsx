"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import AlertCard from "@/components/AlertCard";
import EvidenceDrawer from "@/components/EvidenceDrawer";
import { Alert, api, SEVERITY, Severity } from "@/lib/api";

const TIERS: { key: Severity | "all"; label: string; dotColor?: string }[] = [
  { key: "all", label: "Everything" },
  { key: "critical", label: "Important", dotColor: "bg-accent" },
  { key: "worth_knowing", label: "Worth knowing", dotColor: "bg-peach-deep" },
  { key: "connection", label: "New connections", dotColor: "bg-dusty-deep" },
  { key: "info", label: "Informational", dotColor: "bg-sage-deep" },
];

export default function RadarPage() {
  const [alerts, setAlerts] = useState<Alert[] | null>(null);
  const [tier, setTier] = useState<Severity | "all">("all");
  const [showDismissed, setShowDismissed] = useState(false);
  const [selected, setSelected] = useState<Alert | null>(null);
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<string | null>(null);

  const load = useCallback(() => {
    api.alerts().then((d) => setAlerts(d.alerts)).catch(() => setAlerts([]));
  }, []);

  useEffect(load, [load]);

  const scan = async () => {
    setScanning(true);
    try {
      const result = await api.runMonitor();
      setScanResult(
        `${result.polled_items} item(s) checked · ${result.alerts} alert(s) raised · ` +
          `${result.suppressed} suppressed by verification · ${result.no_match} irrelevant`
      );
      load();
    } finally {
      setScanning(false);
    }
  };

  const dismiss = async (alert: Alert) => {
    await api.dismiss(alert.id);
    load();
  };

  const visible = useMemo(() => {
    if (!alerts) return [];
    return alerts.filter(
      (a) =>
        (tier === "all" || a.severity === tier) &&
        (showDismissed || a.status !== "dismissed")
    );
  }, [alerts, tier, showDismissed]);

  const counts = useMemo(() => {
    const out: Record<string, number> = {};
    (alerts || []).forEach((a) => {
      if (a.status === "dismissed" && !showDismissed) return;
      out[a.severity] = (out[a.severity] || 0) + 1;
    });
    return out;
  }, [alerts, showDismissed]);

  return (
    <div className="space-y-7">
      <section>
        <h1 className="font-serif text-[28px] text-ink">Personal Radar</h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-soft">
          Everything below was found by MOSAIC, not uploaded by you. Each card survived
          entity matching, a skeptical review and a relevance score before it reached this
          page.
        </p>
      </section>

      <section className="flex flex-wrap items-center gap-2">
        {TIERS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTier(t.key)}
            className={`flex items-center gap-1.5 rounded-lg border px-3.5 py-1.5 text-[13px] transition-colors ${
              tier === t.key
                ? "border-ink bg-ink text-paper"
                : "border-line text-ink-soft hover:bg-line/40"
            }`}
          >
            {t.dotColor && (
              <span className={`h-1.5 w-1.5 rounded-full ${t.dotColor}`} />
            )}
            <span>{t.label}</span>
            {t.key !== "all" && counts[t.key] ? (
              <span className="ml-1 opacity-60">{counts[t.key]}</span>
            ) : null}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-3">
          <label className="flex items-center gap-2 text-[13px] text-ink-soft">
            <input
              type="checkbox"
              checked={showDismissed}
              onChange={(e) => setShowDismissed(e.target.checked)}
              className="accent-ink"
            />
            Show dismissed
          </label>
          <button className="btn-ghost" onClick={scan} disabled={scanning}>
            {scanning ? "Scanning…" : "Run a scan now"}
          </button>
        </div>
      </section>

      {scanResult && (
        <p className="rounded-xl border border-line bg-surface px-4 py-2.5 text-[13px] text-ink-soft">
          {scanResult}
        </p>
      )}

      {alerts === null ? (
        <p className="text-sm text-ink-faint">Loading…</p>
      ) : visible.length === 0 ? (
        <div className="card p-10 text-center">
          <p className="font-serif text-lg text-ink">Nothing needs you right now.</p>
          <p className="mt-2 text-sm text-ink-soft">
            That is the intended state: MOSAIC only interrupts when something actually
            affects you.
          </p>
        </div>
      ) : (
        <div className="grid gap-4">
          {visible.map((alert) => (
            <AlertCard
              key={alert.id}
              alert={alert}
              onEvidence={setSelected}
              onDismiss={dismiss}
            />
          ))}
        </div>
      )}

      <EvidenceDrawer alert={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
