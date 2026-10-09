"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import AlertCard from "@/components/AlertCard";
import EvidenceDrawer from "@/components/EvidenceDrawer";
import { Alert, api, DashboardData } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

const STATS = [
  { key: "important", label: "Important", hint: "need your attention", type: "alert" },
  { key: "connections", label: "Connections", hint: "links in your graph", type: "link" },
  { key: "upcoming", label: "Upcoming", hint: "dates ahead", type: "calendar" },
] as const;

export default function DashboardPage() {
  const { user } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Alert | null>(null);
  const [scanning, setScanning] = useState(false);

  const load = useCallback(() => {
    api.dashboard().then(setData).catch((e) => setError(String(e)));
  }, []);

  useEffect(load, [load]);

  const scan = async () => {
    setScanning(true);
    try {
      await api.runMonitor();
      load();
    } finally {
      setScanning(false);
    }
  };

  if (error) {
    return (
      <div className="card p-8">
        <h1 className="font-serif text-xl text-ink">Can&apos;t reach the MOSAIC backend</h1>
        <p className="mt-2 text-sm text-ink-soft">
          Start it with <code className="rounded bg-paper px-1.5 py-0.5">uvicorn app.main:app --reload</code>{" "}
          in the <code className="rounded bg-paper px-1.5 py-0.5">backend</code> folder.
        </p>
        <p className="mt-3 text-xs text-ink-faint">{error}</p>
      </div>
    );
  }

  if (!data) return <p className="text-sm text-ink-faint">Loading…</p>;

  const { summary, recent } = data;
  const userName = user?.name || data.user.name || "there";

  return (
    <div className="space-y-9">
      <section>
        <p className="text-sm text-ink-faint">{greeting()}</p>
        <h1 className="mt-1 font-serif text-[30px] leading-tight text-ink">
          {userName}, here&apos;s what changed.
        </h1>
        <p className="mt-2 max-w-xl text-sm leading-relaxed text-ink-soft">
          MOSAIC is watching {summary.nodes} things you own across {summary.edges} relationships,
          drawn from {summary.documents} documents you handed it.
        </p>
      </section>

      <section className="grid gap-4 sm:grid-cols-3">
        {STATS.map((stat) => (
          <div key={stat.key} className="card p-5">
            <div className="flex items-center justify-between">
              <span className="label">{stat.label}</span>
              {stat.type === "alert" && (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="text-accent">
                  <path d="M12 9v4m0 4h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
              {stat.type === "link" && (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="text-dusty-deep">
                  <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" strokeLinecap="round" strokeLinejoin="round" />
                  <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
              {stat.type === "calendar" && (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="text-sage-deep">
                  <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                  <line x1="16" y1="2" x2="16" y2="6" />
                  <line x1="8" y1="2" x2="8" y2="6" />
                  <line x1="3" y1="10" x2="21" y2="10" />
                </svg>
              )}
            </div>
            <p
              className={`mt-3 font-serif text-[34px] leading-none ${
                stat.key === "important" && summary.important > 0 ? "text-accent" : "text-ink"
              }`}
            >
              {summary[stat.key]}
            </p>
            <p className="mt-1.5 text-[12px] text-ink-faint">{stat.hint}</p>
          </div>
        ))}
      </section>

      {summary.upcoming_items.length > 0 && (
        <section className="card p-5">
          <h2 className="label">Coming up</h2>
          <ul className="mt-3 divide-y divide-line">
            {summary.upcoming_items.map((item, i) => (
              <li key={i} className="flex items-center justify-between py-2.5 text-sm">
                <span className="text-ink">{item.name}</span>
                <span className="text-ink-faint">
                  {item.label} · {item.date}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-serif text-[20px] text-ink">Recent discoveries</h2>
          <div className="flex items-center gap-2">
            <button className="btn-ghost" onClick={scan} disabled={scanning}>
              {scanning ? "Scanning…" : "Run a scan now"}
            </button>
            <Link href="/radar" className="btn-ghost">
              Open Radar
            </Link>
          </div>
        </div>

        {recent.length === 0 ? (
          <div className="card p-8 text-center">
            <p className="text-sm text-ink-soft">
              Nothing yet. Add a receipt or a warranty and MOSAIC will start watching.
            </p>
            <Link href="/add" className="btn-primary mt-4">
              Add something
            </Link>
          </div>
        ) : (
          <div className="grid gap-4">
            {recent.map((alert) => (
              <AlertCard key={alert.id} alert={alert} compact onEvidence={setSelected} />
            ))}
          </div>
        )}
      </section>

      <p className="text-[11px] text-ink-faint">
        Reasoning model: {summary.llm_provider}
        {summary.llm_provider === "offline" &&
          ": deterministic rule-based mode. Set GOOGLE_API_KEY to use Gemini."}
      </p>

      <EvidenceDrawer alert={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
