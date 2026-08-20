"use client";

import Link from "next/link";
import { useState } from "react";

import { TopBar } from "@/components/TopBar";
import { api } from "@/lib/api";

export default function EvaluationPage({ params }: { params: { id: string } }) {
  const [predictions, setPredictions] = useState("i think we should go tomorrow");
  const [references, setReferences] = useState("i think we should go tomorrow");
  const [result, setResult] = useState<{ wer: number; cer: number; sentence_accuracy: number; n: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setError(null);
    try {
      const preds = predictions.split("\n").filter(Boolean);
      const refs = references.split("\n").filter(Boolean);
      setResult(await api.evaluate(preds, refs));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Evaluation failed");
    }
  }

  return (
    <div className="min-h-screen">
      <TopBar />
      <main className="mx-auto max-w-3xl px-6 py-8">
        <Link href={`/projects/${params.id}`} className="text-sm text-accent underline">
          ← Back to workspace
        </Link>
        <h1 className="mt-3 text-2xl font-semibold">Evaluation (WER / CER)</h1>
        <p className="mt-1 text-sm text-muted">
          Compare predicted transcripts to known ground truth (one per line).
        </p>

        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <label className="text-sm">
            Predictions
            <textarea
              value={predictions}
              onChange={(e) => setPredictions(e.target.value)}
              className="mt-1 h-32 w-full rounded border border-border bg-panel p-2 text-sm"
            />
          </label>
          <label className="text-sm">
            References
            <textarea
              value={references}
              onChange={(e) => setReferences(e.target.value)}
              className="mt-1 h-32 w-full rounded border border-border bg-panel p-2 text-sm"
            />
          </label>
        </div>

        <button onClick={run} className="focus-ring mt-4 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-black">
          Compute metrics
        </button>
        {error && <p className="mt-3 text-sm text-bad">⛔ {error}</p>}

        {result && (
          <div className="mt-6 grid grid-cols-3 gap-3 text-center">
            <Metric label="WER" value={result.wer} />
            <Metric label="CER" value={result.cer} />
            <Metric label="Sentence acc." value={result.sentence_accuracy} />
          </div>
        )}
      </main>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-border bg-panel p-4">
      <div className="text-2xl font-semibold">{(value * 100).toFixed(1)}%</div>
      <div className="text-xs text-muted">{label}</div>
    </div>
  );
}
