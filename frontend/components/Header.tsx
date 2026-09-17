"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/graph", label: "Life Graph" },
  { href: "/radar", label: "Radar" },
  { href: "/add", label: "Add" },
];

export default function Header() {
  const pathname = usePathname();
  const [unread, setUnread] = useState<number | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () =>
      api
        .dashboard()
        .then((d) => alive && setUnread(d.summary.unread_alerts))
        .catch(() => alive && setUnread(null));
    load();
    const timer = setInterval(load, 20000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [pathname]);

  return (
    <header className="border-b border-line bg-paper/85 backdrop-blur sticky top-0 z-40">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-5 py-4">
        <Link href="/" className="flex items-baseline gap-2.5">
          <span className="font-serif text-[22px] tracking-[0.16em] text-ink">MOSAIC</span>
          <span className="hidden text-[11px] text-ink-faint sm:inline">
            personal intelligence
          </span>
        </Link>

        <nav className="flex items-center gap-1">
          {NAV.map((item) => {
            const active =
              item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`rounded-lg px-3.5 py-1.5 text-sm transition-colors ${
                  active
                    ? "bg-ink text-paper"
                    : "text-ink-soft hover:bg-line/50 hover:text-ink"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
          <Link
            href="/radar"
            aria-label="Notifications"
            className="relative ml-2 flex h-9 w-9 items-center justify-center rounded-lg border border-line text-ink-soft hover:bg-line/40"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
              <path d="M18 8A6 6 0 1 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M13.7 21a2 2 0 0 1-3.4 0" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            {!!unread && unread > 0 && (
              <span className="absolute -right-1 -top-1 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-accent px-1 text-[10px] font-semibold text-white">
                {unread}
              </span>
            )}
          </Link>
        </nav>
      </div>
    </header>
  );
}
