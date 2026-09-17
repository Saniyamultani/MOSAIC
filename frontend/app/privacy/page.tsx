import Link from "next/link";

export const metadata = {
  title: "Privacy Policy | MOSAIC",
  description: "MOSAIC Privacy Policy and Personal Data Handling Standards",
};

export default function PrivacyPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <header className="border-b border-line pb-6">
        <Link href="/" className="text-xs uppercase tracking-wider text-ink-faint hover:text-ink">
          &larr; Back to Dashboard
        </Link>
        <h1 className="mt-3 font-serif text-[32px] text-ink">Privacy Policy</h1>
        <p className="mt-1 text-sm text-ink-faint">Effective Date: September 14, 2026</p>
      </header>

      <article className="space-y-6 text-sm leading-relaxed text-ink-soft">
        <section>
          <h2 className="font-serif text-xl text-ink">1. Principles & Data Ownership</h2>
          <p className="mt-2">
            MOSAIC is built as a personal intelligence system. You own your data. We do not sell your personal records, documents, purchase receipts, or warranty details to third parties or data brokers.
          </p>
        </section>

        <section>
          <h2 className="font-serif text-xl text-ink">2. Data We Collect and How We Use It</h2>
          <ul className="mt-2 list-disc space-y-2 pl-5">
            <li>
              <strong className="text-ink">Document & Ingestion Data:</strong> When you upload receipts, invoices, or warranty notes, MOSAIC extracts structured metadata (e.g. brand, model, purchase date) to construct your Life Graph.
            </li>
            <li>
              <strong className="text-ink">Monitoring & Public Signals:</strong> MOSAIC cross-references your entity model against public safety notices, manufacturer updates, and service advisories.
            </li>
            <li>
              <strong className="text-ink">Assistant & Chat Data:</strong> Conversation queries are processed strictly to answer your questions or retrieve your saved records.
            </li>
          </ul>
        </section>

        <section>
          <h2 className="font-serif text-xl text-ink">3. Data Security & Storage</h2>
          <p className="mt-2">
            All stored entity models, document extractions, and alerts are secured behind authenticated database endpoints. No external tracking cookies, biometric fingerprinting, or hidden telemetry trackers are deployed on this platform.
          </p>
        </section>

        <section>
          <h2 className="font-serif text-xl text-ink">4. User Rights & Data Deletion</h2>
          <p className="mt-2">
            You retain full authority to review, dismiss, or purge any document, node, or alert from MOSAIC at any time. Upon dismissal or deletion, records are removed from your active graph model.
          </p>
        </section>

        <section className="border-t border-line pt-6">
          <p className="text-xs text-ink-faint">
            Questions regarding our privacy standards can be submitted to privacy@mosaic.internal.
          </p>
        </section>
      </article>
    </div>
  );
}
