"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/graph", label: "Life Graph" },
  { href: "/radar", label: "Radar" },
  { href: "/add", label: "Add" },
];

export default function Header() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
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
  }, [pathname, user]);

  return (
    <header className="border-b border-line bg-paper/85 backdrop-blur sticky top-0 z-40">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-5 py-4">
        <Link href="/" className="flex items-baseline gap-2.5">
          <span className="font-serif text-[22px] tracking-[0.16em] text-ink">MOSAIC</span>
          <span className="hidden text-[11px] text-ink-faint sm:inline">
            personal intelligence
          </span>
        </Link>

        <nav className="flex items-center gap-1.5">
          {NAV.map((item) => {
            const active =
              item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`rounded-lg px-3 py-1.5 text-sm transition-colors ${
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
            className="relative flex h-9 w-9 items-center justify-center rounded-lg border border-line text-ink-soft hover:bg-line/40"
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

          {user ? (
            <div className="flex items-center gap-1 ml-1 pl-1 border-l border-line">
              <Link
                href="/profile"
                className={`flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-sm font-medium transition-colors ${
                  pathname === "/profile"
                    ? "bg-accent/15 text-accent"
                    : "text-ink hover:bg-line/50"
                }`}
              >
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-accent text-[11px] font-bold text-white">
                  {user.name ? user.name.charAt(0).toUpperCase() : "U"}
                </span>
                <span className="hidden sm:inline max-w-[100px] truncate">{user.name}</span>
              </Link>
            </div>
          ) : (
            <Link
              href="/login"
              className="ml-1 rounded-lg border border-line bg-paper px-3 py-1.5 text-sm font-medium text-ink hover:bg-line/50 transition-colors"
            >
              Log In
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
}
