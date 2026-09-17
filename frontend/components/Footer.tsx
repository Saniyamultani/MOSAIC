import Link from "next/link";

export default function Footer() {
  return (
    <footer className="mt-16 border-t border-line bg-paper/60 py-8 text-sm">
      <div className="mx-auto flex w-full max-w-6xl flex-col items-center justify-between gap-4 px-5 sm:flex-row">
        <div className="flex items-center gap-2">
          <span className="font-serif text-base tracking-widest text-ink">MOSAIC</span>
          <span className="text-xs text-ink-faint">| Personal Intelligence Workspace</span>
        </div>

        <div className="flex flex-wrap items-center gap-6 text-xs text-ink-soft">
          <Link href="/privacy" className="hover:text-ink transition-colors">
            Privacy Policy
          </Link>
          <Link href="/terms" className="hover:text-ink transition-colors">
            Terms &amp; Conditions
          </Link>
          <Link href="/domain" className="hover:text-ink transition-colors">
            Custom Domain
          </Link>
        </div>

        <div className="text-xs text-ink-faint">
          &copy; 2026 MOSAIC Systems. All rights reserved.
        </div>
      </div>
    </footer>
  );
}
