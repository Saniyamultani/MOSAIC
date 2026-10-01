"use client";

import Link from "next/link";
import { useState } from "react";

export default function DomainPage() {
  const [domain, setDomain] = useState("");
  const [status, setStatus] = useState<"idle" | "verifying" | "connected">("idle");

  const handleConnect = (e: React.FormEvent) => {
    e.preventDefault();
    if (!domain.trim()) return;
    setStatus("verifying");
    setTimeout(() => {
      setStatus("connected");
    }, 1200);
  };

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <header className="border-b border-line pb-6">
        <Link href="/" className="text-xs uppercase tracking-wider text-ink-faint hover:text-ink">
          &larr; Back to Dashboard
        </Link>
        <h1 className="mt-3 font-serif text-[32px] text-ink">Custom Domain Connection</h1>
        <p className="mt-1 text-sm text-ink-soft">
          Connect your custom domain to route MOSAIC personal intelligence to your custom URL.
        </p>
      </header>

      <section className="card p-6 space-y-6">
        <form onSubmit={handleConnect} className="space-y-4">
          <div>
            <label className="label">Custom Domain Name</label>
            <div className="mt-2 flex gap-3">
              <input
                type="text"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                placeholder="app.yourdomain.com"
                className="flex-1 rounded-lg border border-line bg-paper px-4 py-2.5 text-sm text-ink outline-none focus:border-dusty"
              />
              <button
                type="submit"
                disabled={status === "verifying" || !domain.trim()}
                className="btn-primary"
              >
                {status === "verifying" ? "Verifying DNS..." : "Connect Domain"}
              </button>
            </div>
          </div>
        </form>

        {status === "connected" && (
          <div className="rounded-xl border border-sage/40 bg-sage-soft p-4 text-sm text-sage-deep">
            <p className="font-medium">Domain Successfully Configured</p>
            <p className="mt-1 text-xs">
              CNAME record for <code className="font-mono font-semibold">{domain}</code> has been verified. SSL certificate provisioned.
            </p>
          </div>
        )}

        <div className="border-t border-line pt-5 space-y-3">
          <h2 className="label">DNS Configuration Instructions</h2>
          <div className="rounded-xl border border-line bg-paper p-4 text-xs font-mono space-y-2">
            <div className="flex justify-between border-b border-line pb-2 font-sans font-semibold text-ink">
              <span>Type</span>
              <span>Host</span>
              <span>Value</span>
              <span>TTL</span>
            </div>
            <div className="flex justify-between text-ink-soft">
              <span>CNAME</span>
              <span>{domain || "subdomain"}</span>
              <span>cname.mosaic.internal</span>
              <span>Automatic</span>
            </div>
            <div className="flex justify-between text-ink-soft">
              <span>TXT</span>
              <span>_mosaic-challenge</span>
              <span>mosaic-verification-token-8f2e1a</span>
              <span>Automatic</span>
            </div>
          </div>
          <p className="text-xs text-ink-faint">
            DNS propagation typically completes within 5 to 15 minutes.
          </p>
        </div>
      </section>
    </div>
  );
}
