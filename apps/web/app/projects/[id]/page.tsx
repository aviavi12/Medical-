"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { AvailabilityNotice } from "@/components/AvailabilityNotice";
import { QualityBar } from "@/components/QualityBar";
import { TopBar } from "@/components/TopBar";
import { api } from "@/lib/api";
import type { GazeTimeline, Person, Transcript, Video } from "@/types";

export default function WorkspacePage({ params }: { params: { id: string } }) {
  const videoId = params.id;
  const videoRef = useRef<HTMLVideoElement>(null);

  const [video, setVideo] = useState<Video | null>(null);
  const [status, setStatus] = useState<string>("");
  const [people, setPeople] = useState<Person[]>([]);
  const [selected, setSelected] = useState<Person | null>(null);
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [gaze, setGaze] = useState<GazeTimeline | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshPeople = useCallback(async () => {
    const r = await api.listPeople(videoId);
    setPeople(r.people);
    setStatus(r.status);
  }, [videoId]);

  useEffect(() => {
    api.getVideo(videoId).then(setVideo).catch((e) => setError(e.message));
    refreshPeople().catch(() => undefined);
  }, [videoId, refreshPeople]);

  async function runCoarseScan() {
    setAnalyzing(true);
    setError(null);
    try {
      await api.analyzeVideo(videoId);
      // Backend runs synchronously in dev; poll once then refresh.
      const s = await api.status(videoId);
      setStatus(s.status);
      if (s.error) setError(s.error);
      await refreshPeople();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  }

  async function selectPerson(p: Person) {
    setSelected(p);
    setTranscript(null);
    setGaze(null);
    setError(null);
    try {
      await api.analyzePerson(videoId, p.id);
      setTranscript(await api.transcript(videoId, p.id));
      setGaze(await api.gaze(videoId, p.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Person analysis failed");
    }
  }

  function seek(t: number) {
    if (videoRef.current) {
      videoRef.current.currentTime = t;
      videoRef.current.play().catch(() => undefined);
    }
  }

  // Keyboard shortcuts (§80).
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const v = videoRef.current;
      if (!v) return;
      if (e.key === " " || e.key === "k") {
        e.preventDefault();
        v.paused ? v.play() : v.pause();
      } else if (e.key === "ArrowLeft" || e.key === "j") {
        v.currentTime = Math.max(0, v.currentTime - 3);
      } else if (e.key === "ArrowRight" || e.key === "l") {
        v.currentTime = v.currentTime + 3;
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="min-h-screen">
      <TopBar status={status} />
      <main className="mx-auto grid max-w-7xl grid-cols-1 gap-5 px-5 py-6 lg:grid-cols-[1fr_360px]">
        {/* Left / center: player + gallery */}
        <section className="space-y-5">
          <div className="overflow-hidden rounded-xl border border-border bg-black">
            {video?.media_url ? (
              <video ref={videoRef} src={video.media_url} controls className="w-full" />
            ) : (
              <div className="p-16 text-center text-muted">Loading video…</div>
            )}
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={runCoarseScan}
              disabled={analyzing}
              className="focus-ring rounded-lg bg-accent px-4 py-2 font-medium text-black disabled:opacity-50"
            >
              {analyzing ? "Scanning…" : "Detect people (coarse scan)"}
            </button>
            <Link href={`/projects/${videoId}/evaluation`} className="text-sm text-accent underline">
              Evaluation
            </Link>
            {video && (
              <span className="text-xs text-muted">
                {video.metadata.width}×{video.metadata.height} ·{" "}
                {video.metadata.has_audio ? "has audio" : "no audio"}
              </span>
            )}
          </div>

          {error && (
            <div className="rounded-md border border-bad bg-panel2 p-3 text-sm text-bad">⛔ {error}</div>
          )}

          <div>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted">
              People gallery
            </h2>
            {people.length === 0 ? (
              <p className="text-sm text-muted">
                No people yet. Run the coarse scan to detect people.
              </p>
            ) : (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {people.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => p.selectable && selectPerson(p)}
                    className={`focus-ring rounded-lg border p-3 text-left ${
                      selected?.id === p.id ? "border-accent" : "border-border"
                    } bg-panel ${p.selectable ? "hover:border-accent" : "opacity-70"}`}
                  >
                    <div className="flex items-center gap-2">
                      {p.thumbnail_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={p.thumbnail_url} alt={p.label} className="h-12 w-12 rounded object-cover" />
                      ) : (
                        <div className="h-12 w-12 rounded bg-panel2" />
                      )}
                      <div>
                        <div className="font-medium">{p.label}</div>
                        <div className="text-xs text-muted">{p.screen_time.toFixed(1)}s on screen</div>
                      </div>
                    </div>
                    <div className="mt-2 space-y-1">
                      <QualityBar label="Face quality" value={p.face_quality} />
                      <QualityBar label="Lip readiness" value={p.lip_readiness} />
                    </div>
                    {!p.selectable && p.reason && (
                      <p className="mt-2 text-xs text-warn">{p.reason}</p>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        </section>

        {/* Right: selected person */}
        <aside className="space-y-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">Selected person</h2>
          {!selected ? (
            <p className="text-sm text-muted">Select a person to analyze their speech and gaze.</p>
          ) : (
            <div className="space-y-4">
              <div className="rounded-lg border border-border bg-panel p-4">
                <div className="flex items-center gap-3">
                  {selected.thumbnail_url && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={selected.thumbnail_url} alt={selected.label} className="h-14 w-14 rounded object-cover" />
                  )}
                  <div>
                    <div className="font-semibold">{selected.label}</div>
                    <div className="text-xs text-muted">
                      Visibility {selected.visibility}% · quality {selected.face_quality.toFixed(0)}
                    </div>
                  </div>
                </div>
                <Link
                  href={`/projects/${videoId}/person/${selected.id}`}
                  className="mt-3 inline-block text-xs text-accent underline"
                >
                  Open detailed view →
                </Link>
              </div>

              {/* Transcript */}
              <div className="rounded-lg border border-border bg-panel p-4">
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="text-sm font-semibold">Transcript</h3>
                  {transcript?.model_version && (
                    <span className="text-[10px] text-muted">{transcript.model_version}</span>
                  )}
                </div>
                {transcript && <AvailabilityNotice availability={transcript.availability} />}
                {transcript?.segments.length ? (
                  <ul className="mt-2 space-y-2">
                    {transcript.segments.map((s, i) => (
                      <li key={i}>
                        <button
                          onClick={() => seek(s.start_time)}
                          className="focus-ring block w-full rounded p-2 text-left hover:bg-panel2"
                        >
                          <div className="flex justify-between text-xs text-muted">
                            <span>{fmt(s.start_time)}</span>
                            <span className={s.uncertain ? "text-warn" : "text-good"}>
                              {(s.confidence * 100).toFixed(0)}%
                            </span>
                          </div>
                          <div className={s.uncertain ? "confidence-low text-warn" : ""}>{s.text}</div>
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : (
                  transcript && <p className="mt-2 text-sm text-muted">No transcript segments.</p>
                )}
              </div>

              {/* Gaze */}
              <div className="rounded-lg border border-border bg-panel p-4">
                <h3 className="mb-2 text-sm font-semibold">Gaze timeline</h3>
                {gaze && <AvailabilityNotice availability={gaze.availability} />}
                {gaze?.segments.length ? (
                  <ul className="mt-2 space-y-1 text-sm">
                    {gaze.segments.map((g, i) => (
                      <li key={i}>
                        <button
                          onClick={() => seek(g.start)}
                          className="focus-ring flex w-full justify-between rounded px-2 py-1 hover:bg-panel2"
                        >
                          <span className="text-muted">
                            {fmt(g.start)}–{fmt(g.end)}
                          </span>
                          <span>{g.direction}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : (
                  gaze && <p className="mt-2 text-sm text-muted">No gaze data.</p>
                )}
              </div>

              {/* Exports + TTS */}
              <div className="rounded-lg border border-border bg-panel p-4">
                <h3 className="mb-2 text-sm font-semibold">Export</h3>
                <div className="flex flex-wrap gap-2">
                  {["srt", "txt", "json", "report"].map((fmtName) => (
                    <a
                      key={fmtName}
                      href={api.exportUrl(videoId, selected.id, fmtName)}
                      className="rounded border border-border px-3 py-1 text-xs hover:border-accent"
                    >
                      {fmtName.toUpperCase()}
                    </a>
                  ))}
                </div>
              </div>
            </div>
          )}
        </aside>
      </main>
    </div>
  );
}

function fmt(t: number): string {
  const m = Math.floor(t / 60);
  const s = (t % 60).toFixed(1);
  return `${m}:${s.padStart(4, "0")}`;
}
