"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { api, DocumentEvaluation, ExtractionResult, formatFieldLabel } from "@/lib/api";

const EXAMPLES = [
  "I bought a Samsung Galaxy S26 Ultra (SM-S926B) from Amazon for Rs 79,999 on 12 May 2026, paid with my HDFC card.",
  "Samsung Care+ extended warranty for Galaxy S26 Ultra, model SM-S926B, 24 months from 12 May 2026.",
  "Netflix Premium plan Rs 649 per month, renews on 18 September 2026, charged to HDFC card.",
];

const KINDS = [
  { value: "", label: "Let MOSAIC decide" },
  { value: "receipt", label: "Receipt" },
  { value: "warranty", label: "Warranty" },
  { value: "bill", label: "Bill" },
  { value: "subscription", label: "Subscription" },
  { value: "calendar_event", label: "Calendar event" },
];

type Mode = "text" | "file";

export default function AddPage() {
  const [mode, setMode] = useState<Mode>("text");
  const [text, setText] = useState("");
  const [kind, setKind] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ExtractionResult | null>(null);
  const [fields, setFields] = useState<Record<string, any>>({});
  const [confirmed, setConfirmed] = useState<any>(null);
  const [evaluation, setEvaluation] = useState<DocumentEvaluation | null>(null);
  const [evaluationLoading, setEvaluationLoading] = useState(false);
  const [evaluationError, setEvaluationError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const reset = () => {
    setResult(null);
    setConfirmed(null);
    setFields({});
    setError(null);
    setEvaluation(null);
    setEvaluationError(null);
    setEvaluationLoading(false);
  };

  const extract = async () => {
    reset();
    setBusy(true);
    try {
      let res: ExtractionResult;
      if (mode === "file") {
        const file = fileRef.current?.files?.[0];
        if (!file) throw new Error("Choose a file first");
        res = await api.ingestFile(file, kind || undefined);
      } else {
        res = await api.ingestText(text, kind || undefined);
      }
      setResult(res);
      setFields(res.document.extraction.fields || {});
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const confirm = async () => {
    if (!result) return;
    setBusy(true);
    try {
      const res = await api.confirm(result.document.id, result.thread_id, fields);
      setConfirmed(res);
      setEvaluationLoading(true);
      try {
        setEvaluation(await api.evaluateDocument(result.document.id));
      } catch (e) {
        setEvaluationError(String(e));
      } finally {
        setEvaluationLoading(false);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-7">
      <section>
        <h1 className="font-serif text-[28px] text-ink">Hand MOSAIC something</h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-soft">
          A receipt, a warranty, a bill, a subscription email, or just a sentence. MOSAIC
          pulls out the details and asks you to confirm once: that is the only manual step.
        </p>
      </section>

      <section className="card p-6">
        <div className="flex flex-wrap gap-2">
          {(["text", "file"] as Mode[]).map((m) => (
            <button
              key={m}
              onClick={() => {
                setMode(m);
                reset();
              }}
              className={`rounded-lg border px-3.5 py-1.5 text-[13px] ${
                mode === m
                  ? "border-ink bg-ink text-paper"
                  : "border-line text-ink-soft hover:bg-paper"
              }`}
            >
              {m === "text" ? "Type text" : "Upload file"}
            </button>
          ))}
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            className="ml-auto rounded-lg border border-line bg-surface px-3.5 py-1.5 text-[13px] text-ink-soft"
          >
            {KINDS.map((k) => (
              <option key={k.value} value={k.value}>
                {k.label}
              </option>
            ))}
          </select>
        </div>

        <div className="mt-5">
          {mode === "text" && (
            <>
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={5}
                placeholder="I bought a Samsung Galaxy S26 from Amazon for ₹79,999…"
                className="w-full resize-y rounded-xl border border-line bg-paper px-4 py-3 text-sm text-ink outline-none focus:border-dusty"
              />
              <div className="mt-3 flex flex-wrap gap-2">
                {EXAMPLES.map((example, i) => (
                  <button
                    key={i}
                    onClick={() => setText(example)}
                    className="rounded-md border border-line px-3 py-1 text-[12px] text-ink-faint hover:bg-paper"
                  >
                    Example {i + 1}
                  </button>
                ))}
              </div>
            </>
          )}

          {mode === "file" && (
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.webp,.bmp,.tiff,.txt,.md,.csv,.eml,.ics,.html"
              className="block w-full rounded-xl border border-dashed border-line bg-paper px-4 py-8 text-sm text-ink-soft file:mr-4 file:rounded-lg file:border-0 file:bg-ink file:px-4 file:py-2 file:text-sm file:text-paper"
            />
          )}
        </div>

        <button className="btn-primary mt-5" onClick={extract} disabled={busy}>
          {busy ? "Reading…" : "Extract details"}
        </button>
        {error && <p className="mt-3 text-sm text-accent">{error}</p>}
      </section>

      {result && !confirmed && (
        <section className="card p-6">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="font-serif text-[20px] text-ink">
              I found these details. Is everything correct?
            </h2>
            <span className="chip border-dusty/40 bg-dusty-soft text-dusty-deep">
              {result.document.extraction.kind}
            </span>
            <span className="ml-auto text-[12px] text-ink-faint">
              {Math.round((result.document.extraction.confidence || 0) * 100)}% extraction
              confidence
            </span>
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            {Object.entries(fields)
              .filter(([key]) => key !== "model_codes")
              .map(([key, value]) => (
              <label key={key} className="block">
                <span className="label">{formatFieldLabel(key)}</span>
                <input
                  value={Array.isArray(value) ? value.join(", ") : String(value ?? "")}
                  onChange={(e) =>
                    setFields((prev) => ({ ...prev, [key]: e.target.value }))
                  }
                  className="mt-1 w-full rounded-lg border border-line bg-paper px-3 py-2 text-sm text-ink outline-none focus:border-dusty"
                />
              </label>
            ))}
            {Object.keys(fields).length === 0 && (
              <p className="text-sm text-ink-soft">
                Nothing structured came out of that. Try adding the product, seller, price
                and date.
              </p>
            )}
          </div>

          <div className="mt-6 flex items-center gap-2">
            <button className="btn-primary" onClick={confirm} disabled={busy}>
              Confirm details
            </button>
            <button className="btn-ghost" onClick={reset}>
              Discard
            </button>
          </div>

          {result.trace.length > 0 && (
            <details className="mt-5">
              <summary className="cursor-pointer text-[12px] text-ink-faint">
                What the Ingestion Agent did
              </summary>
              <ul className="mt-2 space-y-1.5">
                {result.trace.map((step, i) => (
                  <li key={i} className="text-[13px] text-ink-soft">
                    <span className="text-ink-faint">{step.agent} · </span>
                    {step.detail}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </section>
      )}

      {confirmed && (
        <section className="card p-6">
          <h2 className="font-serif text-[20px] text-ink">Added to your Life Graph</h2>
          <p className="mt-2 text-sm text-ink-soft">
            {confirmed.created} new node(s), {confirmed.merged} merged into things MOSAIC
            already knew about, {confirmed.edges} relationship(s).
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {(confirmed.entities || []).map((e: any) => (
              <span
                key={e.id}
                className="rounded-md border border-line bg-paper px-3 py-1 text-[12px] text-ink-soft"
              >
                {e.name}
              </span>
            ))}
          </div>
          {(confirmed.connections || []).length > 0 && (
            <div className="mt-4 rounded-xl border border-dusty/40 bg-dusty-soft px-4 py-3">
              <span className="label text-dusty-deep">New connection found</span>
              {confirmed.connections.map((c: any, i: number) => (
                <p key={i} className="mt-1 text-[13px] text-dusty-deep">
                  {c.entity} ↔ {c.related}
                </p>
              ))}
            </div>
          )}
          <div className="mt-5 rounded-xl border border-line bg-paper/70 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h3 className="font-semibold text-ink">RAGAS-style retrieval evaluation</h3>
                <p className="mt-0.5 text-xs text-ink-faint">
                  Post-upload retrieval checks for this document
                </p>
              </div>
              {evaluation && (
                <span
                  className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                    evaluation.checks.every((check) => check.passed)
                      ? "bg-emerald-100 text-emerald-800"
                      : "bg-amber-100 text-amber-900"
                  }`}
                >
                  {evaluation.checks.every((check) => check.passed) ? "Checks passed" : "Review checks"}
                </span>
              )}
            </div>
            {evaluationLoading && (
              <p className="mt-3 text-sm text-ink-soft">Checking the private retrieval index…</p>
            )}
            {evaluationError && (
              <p role="alert" className="mt-3 text-sm text-red-700">
                Evaluation could not be completed: {evaluationError}
              </p>
            )}
            {evaluation && (
              <>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  {[
                    {
                      label: "Context precision",
                      value: evaluation.metrics.context_precision,
                      detail: evaluation.metrics.context_precision_definition,
                    },
                    {
                      label: "Context recall",
                      value: evaluation.metrics.context_recall,
                      detail: evaluation.metrics.context_recall_definition,
                    },
                  ].map((metric) => (
                    <div key={metric.label} className="rounded-lg border border-line/70 bg-white/70 p-3">
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-faint">
                        {metric.label}
                      </p>
                      <p className="mt-1 font-serif text-2xl text-ink">
                        {(metric.value * 100).toFixed(0)}%
                      </p>
                      <p className="mt-1 text-[11px] leading-relaxed text-ink-soft">{metric.detail}</p>
                    </div>
                  ))}
                </div>
                <ul className="mt-3 space-y-2">
                  {evaluation.checks.map((check) => (
                    <li key={check.name} className="flex gap-2 text-sm">
                      <span className={check.passed ? "text-emerald-700" : "text-amber-700"}>
                        {check.passed ? "✓" : "!"}
                      </span>
                      <span>
                        <span className="font-medium text-ink">{check.name}:</span>{" "}
                        <span className="text-ink-soft">{check.actual}</span>
                      </span>
                    </li>
                  ))}
                </ul>
                {evaluation.retrieved_documents.length > 0 && (
                  <details className="mt-3">
                    <summary className="cursor-pointer text-xs font-medium text-ink-soft">
                      Retrieved document evidence ({evaluation.retrieved_documents.length})
                    </summary>
                    <ul className="mt-2 space-y-1 text-xs text-ink-faint">
                      {evaluation.retrieved_documents.map((document, index) => (
                        <li key={document.document_id}>
                          {index + 1}. {document.title} · similarity {document.score.toFixed(3)}
                          {document.matches_uploaded_document ? " · this upload" : ""}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
                <p className="mt-3 border-t border-line/60 pt-3 text-[11px] leading-relaxed text-ink-faint">
                  {evaluation.note}
                </p>
              </>
            )}
          </div>
          <div className="mt-5 flex gap-2">
            <Link href="/graph" className="btn-primary">
              Open the Life Graph
            </Link>
            <button className="btn-ghost" onClick={reset}>
              Add another
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
