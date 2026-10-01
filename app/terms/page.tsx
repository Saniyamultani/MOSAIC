import Link from "next/link";

export const metadata = {
  title: "Terms & Conditions | MOSAIC",
  description: "MOSAIC Terms and Conditions of Service",
};

export default function TermsPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <header className="border-b border-line pb-6">
        <Link href="/" className="text-xs uppercase tracking-wider text-ink-faint hover:text-ink">
          &larr; Back to Dashboard
        </Link>
        <h1 className="mt-3 font-serif text-[32px] text-ink">Terms and Conditions</h1>
        <p className="mt-1 text-sm text-ink-faint">Effective Date: September 14, 2026</p>
      </header>

      <article className="space-y-6 text-sm leading-relaxed text-ink-soft">
        <section>
          <h2 className="font-serif text-xl text-ink">1. Acceptance of Terms</h2>
          <p className="mt-2">
            By accessing or using the MOSAIC platform, you agree to abide by these Terms and Conditions. MOSAIC provides a personal intelligence workspace designed to organize personal records, track warranties, and monitor external announcements relevant to your items.
          </p>
        </section>

        <section>
          <h2 className="font-serif text-xl text-ink">2. Accuracy & Verification</h2>
          <p className="mt-2">
            MOSAIC automated agents extract structured metadata from submitted documents and match public announcements. While verification checks and skeptic filters reduce false positives, you should verify critical recall or legal claims directly with manufacturers before taking action.
          </p>
        </section>

        <section>
          <h2 className="font-serif text-xl text-ink">3. Acceptable Use</h2>
          <p className="mt-2">
            You agree to upload only documents and files that you own or have explicit authorization to process. You may not use MOSAIC to upload illegal material, attempt unauthorized access to infrastructure, or scrape platform resources.
          </p>
        </section>

        <section>
          <h2 className="font-serif text-xl text-ink">4. Limitation of Liability</h2>
          <p className="mt-2">
            MOSAIC is provided as an intelligence management tool. MOSAIC is not responsible for missed third-party manufacturer deadlines, unverified retailer policy changes, or external service outages.
          </p>
        </section>

        <section className="border-t border-line pt-6">
          <p className="text-xs text-ink-faint">
            For terms inquiries, contact legal@mosaic.internal.
          </p>
        </section>
      </article>
    </div>
  );
}
