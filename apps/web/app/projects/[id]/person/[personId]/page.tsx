"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AvailabilityNotice } from "@/components/AvailabilityNotice";
import { QualityBar } from "@/components/QualityBar";
import { TopBar } from "@/components/TopBar";
import { api } from "@/lib/api";
import type { GazeTimeline, Person, Transcript } from "@/types";

export default function PersonDetailPage({
  params,
}: {
  params: { id: string; personId: string };
}) {
  const { id: videoId, personId } = params;
  const [person, setPerson] = useState<Person | null>(null);
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [gaze, setGaze] = useState<GazeTimeline | null>(null);
  const [raw, setRaw] = useState(false);
  const [tts, setTts] = useState<{ url: string | null; label: string; state: string } | null>(null);

  useEffect(() => {
    api.listPeople(videoId).then((r) => setPerson(r.people.find((p) => p.id === personId) || null));
    api.transcript(videoId, personId).then(setTranscript).catch(() => undefined);
    api.gaze(videoId, personId).then(setGaze).catch(() => undefined);
  }, [videoId, personId]);

  async function synth() {
    const r = await api.tts(videoId, personId);
    setTts({ url: r.url, label: r.label, state: r.availability.state });
  }

  return (
    <div className="min-h-screen">
      <TopBar />
      <main className="mx-auto max-w-5xl px-6 py-8">
        <Link href={`/projects/${videoId}`} className="text-sm text-accent underline">
          ← Back to workspace
        </Link>
        <h1 className="mt-3 text-2xl font-semibold">{person?.label ?? "Person"}</h1>

        {person && (
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <QualityBar label="Face quality" value={person.face_quality} />
            <QualityBar label="Lip readiness" value={person.lip_readiness} />
            <QualityBar label="Visibility" value={person.visibility} suffix="%" />
            <QualityBar label="Screen time" value={Math.min(100, person.screen_time)} suffix="s" max={100} />
          </div>
        )}

        <section className="mt-8">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-lg font-semibold">Transcript</h2>
            <label className="flex items-center gap-2 text-xs text-muted">
              <input type="checkbox" checked={raw} onChange={(e) => setRaw(e.target.checked)} />
              Show raw visual transcript
            </label>
          </div>
          {transcript && <AvailabilityNotice availability={transcript.availability} />}
          <ul className="mt-2 space-y-2">
            {transcript?.segments.map((s, i) => (
              <li key={i} className="rounded border border-border bg-panel p-3">
                <div className="flex justify-between text-xs text-muted">
                  <span>
                    {s.start_time.toFixed(2)}s – {s.end_time.toFixed(2)}s
                  </span>
                  <span className={s.uncertain ? "text-warn" : "text-good"}>
                    {(s.confidence * 100).toFixed(0)}% confidence
                  </span>
                </div>
                <div className={`mt-1 ${s.uncertain ? "confidence-low text-warn" : ""}`}>
                  {raw ? s.raw_text || s.text : s.processed_text || s.text}
                </div>
                {s.alternatives.length > 0 && (
                  <div className="mt-1 text-xs text-muted">
                    Alternatives:{" "}
                    {s.alternatives.map((a) => `${a.text} (${(a.confidence * 100).toFixed(0)}%)`).join(", ")}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </section>

        <section className="mt-8">
          <h2 className="text-lg font-semibold">Gaze</h2>
          {gaze && <AvailabilityNotice availability={gaze.availability} />}
          <ul className="mt-2 grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
            {gaze?.segments.map((g, i) => (
              <li key={i} className="rounded border border-border bg-panel px-3 py-2">
                <span className="text-muted">
                  {g.start.toFixed(1)}–{g.end.toFixed(1)}s
                </span>{" "}
                → {g.direction}
              </li>
            ))}
          </ul>
        </section>

        <section className="mt-8 space-y-3">
          <h2 className="text-lg font-semibold">Synthetic speech (optional)</h2>
          <p className="text-sm text-muted">
            Generic synthetic voice only. Never clones a real person&apos;s voice.
          </p>
          <button onClick={synth} className="focus-ring rounded-lg bg-accent px-4 py-2 text-sm font-medium text-black">
            Generate synthetic audio
          </button>
          {tts && (
            <div className="text-sm">
              <p className="text-muted">{tts.label}</p>
              {tts.url && tts.state === "REAL_RESULT" ? (
                <audio controls src={tts.url} className="mt-2 w-full" />
              ) : (
                <p className="mt-1 text-warn">Audio unavailable ({tts.state}).</p>
              )}
            </div>
          )}
        </section>

        <section className="mt-8">
          <h2 className="text-lg font-semibold">Export</h2>
          <div className="mt-2 flex flex-wrap gap-2">
            {["srt", "txt", "json", "csv", "report"].map((f) => (
              <a
                key={f}
                href={api.exportUrl(videoId, personId, f)}
                className="rounded border border-border px-3 py-1 text-xs hover:border-accent"
              >
                {f.toUpperCase()}
              </a>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
