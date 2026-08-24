"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { AvailabilityNotice } from "@/components/AvailabilityNotice";
import { QualityBar } from "@/components/QualityBar";
import { TopBar } from "@/components/TopBar";
import { api } from "@/lib/api";
import { confidenceClass, confidenceLevel } from "@/lib/confidence";
import type {
  DebugCrops,
  GazeTimeline,
  Person,
  PersonEvalResult,
  ReadinessStatus,
  Transcript,
  TranscriptSegment,
  Video,
} from "@/types";

type ModelsInfo = Awaited<ReturnType<typeof api.models>>;

const NO_SPEECH = "[no speech evidence]";

function statusColor(status: ReadinessStatus): string {
  if (status === "READY") return "border-good text-good";
  if (status === "WARNING") return "border-warn text-warn";
  return "border-bad text-bad";
}

function StatusBadge({ status }: { status: ReadinessStatus }) {
  return (
    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${statusColor(status)}`}>
      {status}
    </span>
  );
}

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
  const [analyzingPerson, setAnalyzingPerson] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [personError, setPersonError] = useState<string | null>(null);
  const [models, setModels] = useState<ModelsInfo | null>(null);

  // Debug + evaluation (developer tools).
  const [debug, setDebug] = useState<DebugCrops | null>(null);
  const [showDebug, setShowDebug] = useState(false);
  const [devMode, setDevMode] = useState(false);
  const [evalGt, setEvalGt] = useState("");
  const [evalResult, setEvalResult] = useState<PersonEvalResult | null>(null);
  const [evaluating, setEvaluating] = useState(false);

  const refreshPeople = useCallback(async () => {
    const r = await api.listPeople(videoId);
    setPeople(r.people);
    setStatus(r.status);
  }, [videoId]);

  useEffect(() => {
    api.getVideo(videoId).then(setVideo).catch((e) => setError(e.message));
    api.models().then(setModels).catch(() => undefined);
    refreshPeople().catch(() => undefined);
  }, [videoId, refreshPeople]);

  async function runCoarseScan() {
    setAnalyzing(true);
    setError(null);
    try {
      await api.analyzeVideo(videoId);
      const s = await api.status(videoId);
      setStatus(s.status);
      if (s.error) setError(s.error);
      await refreshPeople();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Coarse scan could not complete.");
    } finally {
      setAnalyzing(false);
    }
  }

  // Selecting a person no longer auto-runs analysis — the user clicks
  // "Analyze speech" explicitly (§2). If a transcript already exists we show it.
  async function selectPerson(p: Person) {
    setSelected(p);
    setTranscript(null);
    setGaze(null);
    setPersonError(null);
    setDebug(null);
    setShowDebug(false);
    setEvalResult(null);
    try {
      const t = await api.transcript(videoId, p.id);
      if (t.segments.length) {
        setTranscript(t);
        setGaze(await api.gaze(videoId, p.id).catch(() => null));
      }
    } catch {
      /* no prior transcript — expected */
    }
  }

  async function analyzeSpeech(override = false) {
    if (!selected) return;
    setAnalyzingPerson(true);
    setPersonError(null);
    setTranscript(null);
    try {
      const res = await api.analyzePerson(videoId, selected.id, override);
      if (res.state === "REAL_RESULT") {
        setTranscript(await api.transcript(videoId, selected.id));
        setGaze(await api.gaze(videoId, selected.id).catch(() => null));
      } else {
        // Honest, specific reason — never a bare "Analysis failed" (§24).
        setPersonError(res.detail || `No transcript produced (${res.state}).`);
        setTranscript(await api.transcript(videoId, selected.id).catch(() => null));
      }
    } catch (e) {
      setPersonError(e instanceof Error ? e.message : "Speech analysis could not complete.");
    } finally {
      setAnalyzingPerson(false);
    }
  }

  async function loadDebug() {
    if (!selected) return;
    setShowDebug(true);
    try {
      setDebug(await api.debugCrops(videoId, selected.id, 4));
    } catch (e) {
      setDebug({
        video_id: videoId, person_id: selected.id, available: false,
        note: e instanceof Error ? e.message : "Could not build debug crops.",
        crop_mode: null, frames: [], sequence_url: null,
      });
    }
  }

  async function runEvaluation() {
    if (!selected || !evalGt.trim()) return;
    setEvaluating(true);
    try {
      setEvalResult(await api.evaluatePerson(videoId, selected.id, evalGt, false));
    } catch (e) {
      setPersonError(e instanceof Error ? e.message : "Evaluation failed.");
    } finally {
      setEvaluating(false);
    }
  }

  function seek(t: number) {
    if (videoRef.current) {
      videoRef.current.currentTime = t;
      videoRef.current.play().catch(() => undefined);
    }
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const v = videoRef.current;
      if (!v) return;
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "TEXTAREA" || tag === "INPUT") return;
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
      <main className="mx-auto grid max-w-7xl grid-cols-1 gap-5 px-5 py-6 lg:grid-cols-[1fr_380px]">
        {/* Left / center: player + gallery */}
        <section className="space-y-5">
          <div className="overflow-hidden rounded-xl border border-border bg-black">
            {video?.media_url ? (
              <video ref={videoRef} src={video.media_url} controls className="w-full" />
            ) : (
              <div className="p-16 text-center text-muted">Loading video…</div>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={runCoarseScan}
              disabled={analyzing}
              className="focus-ring rounded-lg bg-accent px-4 py-2 font-medium text-black disabled:opacity-50"
            >
              {analyzing ? "Scanning…" : "Scan for people"}
            </button>
            <Link href={`/projects/${videoId}/evaluation`} className="text-sm text-accent underline">
              Batch evaluation
            </Link>
            <label className="ml-auto flex items-center gap-2 text-xs text-muted">
              <input type="checkbox" checked={devMode} onChange={(e) => setDevMode(e.target.checked)} />
              Developer tools
            </label>
          </div>

          {/* Visual-only lip reading is the default and only mode: the audio track is
              never passed to the ML pipeline. */}
          {video && (
            <div className="flex flex-wrap items-center gap-3 text-xs">
              <span className="rounded-full border border-good px-2 py-1 text-good">
                ✓ Visual-only mode: ACTIVE
              </span>
              {models && (
                <span className="rounded-full border border-accent px-2 py-1 text-accent">
                  Model: {models.models.find((m) => m.active)?.display_name ?? models.active_model} ·{" "}
                  {models.active_open_vocabulary ? "OPEN-vocabulary English" : "CLOSED vocab (benchmark)"} ·{" "}
                  {models.device.device.toUpperCase()}
                </span>
              )}
              <span className="text-muted">
                Audio: <strong>{video.metadata.has_audio ? "Present (ignored)" : "None"}</strong>
                {video.metadata.has_audio && " — transcript is visual-only"}
              </span>
              <span className="text-muted">
                {video.metadata.width}×{video.metadata.height}
                {video.metadata.fps ? ` · ${Math.round(video.metadata.fps)}fps` : ""}
              </span>
            </div>
          )}

          {error && (
            <div className="rounded-md border border-bad bg-panel2 p-3 text-sm text-bad">⛔ {error}</div>
          )}

          <div>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted">
              People gallery
            </h2>
            {people.length === 0 ? (
              <p className="text-sm text-muted">
                No people detected yet. Run “Scan for people” to detect everyone in the video.
              </p>
            ) : (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {people.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => selectPerson(p)}
                    className={`focus-ring rounded-lg border p-3 text-left ${
                      selected?.id === p.id ? "border-accent" : "border-border"
                    } bg-panel hover:border-accent`}
                  >
                    <div className="flex items-center gap-2">
                      {p.thumbnail_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={p.thumbnail_url} alt={p.label} className="h-12 w-12 rounded object-cover" />
                      ) : (
                        <div className="h-12 w-12 rounded bg-panel2" />
                      )}
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{p.label}</span>
                          <StatusBadge status={p.status} />
                        </div>
                        <div className="text-xs text-muted">
                          {p.screen_time.toFixed(1)}s · face ~{Math.round(p.quality_report?.avg_face_width_px ?? 0)}px
                        </div>
                      </div>
                    </div>
                    <div className="mt-2 space-y-1">
                      <QualityBar label="Face quality" value={p.face_quality} />
                      <QualityBar label="Lip-reading readiness" value={p.lip_readiness} />
                    </div>
                    {p.reason && (
                      <p className={`mt-2 text-xs ${p.status === "INSUFFICIENT" ? "text-bad" : "text-warn"}`}>
                        {p.reason}
                      </p>
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
            <p className="text-sm text-muted">
              Select a person, then run “Analyze speech” to transcribe their visible speech.
            </p>
          ) : (
            <div className="space-y-4">
              <div className="rounded-lg border border-border bg-panel p-4">
                <div className="flex items-center gap-3">
                  {selected.thumbnail_url && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={selected.thumbnail_url} alt={selected.label} className="h-14 w-14 rounded object-cover" />
                  )}
                  <div>
                    <div className="flex items-center gap-2 font-semibold">
                      {selected.label} <StatusBadge status={selected.status} />
                    </div>
                    <div className="text-xs text-muted">
                      Readiness {selected.lip_readiness.toFixed(0)}/100 · visible {selected.visibility}%
                    </div>
                  </div>
                </div>

                {/* Full per-person quality report (§25). */}
                {selected.quality_report && (
                  <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
                    <QRow label="Face quality" value={`${selected.quality_report.face_quality_score.toFixed(0)}/100`} />
                    <QRow label="Lip readiness" value={`${selected.quality_report.lip_readiness_score.toFixed(0)}/100`} />
                    <QRow label="Usable time" value={`${selected.quality_report.usable_duration.toFixed(1)}s`} />
                    <QRow label="Avg face width" value={`${selected.quality_report.avg_face_width_px.toFixed(0)}px`} />
                    <QRow label="Mouth visible" value={`${selected.quality_report.avg_mouth_visibility_pct.toFixed(0)}%`} />
                    <QRow label="Sharpness" value={selected.quality_report.avg_sharpness.toFixed(2)} />
                    <QRow label="Pose (frontal)" value={selected.quality_report.avg_pose_quality.toFixed(2)} />
                    <QRow label="Tracking" value={`${(selected.quality_report.tracking_stability * 100).toFixed(0)}%`} />
                  </dl>
                )}
                {selected.quality_report?.reasons?.length ? (
                  <ul className="mt-2 list-disc space-y-0.5 pl-4 text-[11px] text-warn">
                    {selected.quality_report.reasons.map((r, i) => <li key={i}>{r}</li>)}
                  </ul>
                ) : null}

                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    onClick={() => analyzeSpeech(selected.status === "INSUFFICIENT")}
                    disabled={analyzingPerson}
                    className="focus-ring rounded-lg bg-accent px-4 py-2 text-sm font-medium text-black disabled:opacity-50"
                  >
                    {analyzingPerson
                      ? "Analyzing…"
                      : selected.status === "INSUFFICIENT"
                        ? "Analyze anyway (low quality)"
                        : "Analyze speech"}
                  </button>
                  <Link
                    href={`/projects/${videoId}/person/${selected.id}`}
                    className="focus-ring rounded-lg border border-border px-3 py-2 text-xs hover:border-accent"
                  >
                    Detailed view →
                  </Link>
                </div>
                <p className="mt-2 text-[11px] text-muted">
                  Open-vocabulary English visual speech recognition. Lip reading is probabilistic —
                  results are estimates from visible mouth movement, not certain transcription.
                </p>
              </div>

              {personError && (
                <div className="rounded-md border border-warn bg-panel2 p-3 text-xs text-warn">
                  {personError}
                </div>
              )}

              {/* Transcript */}
              <div className="rounded-lg border border-border bg-panel p-4">
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="text-sm font-semibold">Visual speech transcription</h3>
                  {transcript?.model_version && (
                    <span className="text-[10px] text-muted">{transcript.model_version}</span>
                  )}
                </div>
                {transcript && <AvailabilityNotice availability={transcript.availability} />}
                {transcript?.segments.length ? (
                  <ul className="mt-2 space-y-2">
                    {transcript.segments.map((s, i) => (
                      <SegmentRow key={i} s={s} onSeek={() => seek(s.start_time)} />
                    ))}
                  </ul>
                ) : (
                  transcript && <p className="mt-2 text-sm text-muted">No transcript segments.</p>
                )}
              </div>

              {/* Debug mode (§12) */}
              <div className="rounded-lg border border-border bg-panel p-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold">Debug: what the model sees</h3>
                  <button
                    onClick={showDebug ? () => setShowDebug(false) : loadDebug}
                    className="focus-ring rounded border border-border px-2 py-1 text-[11px] hover:border-accent"
                  >
                    {showDebug ? "Hide" : "Show crops"}
                  </button>
                </div>
                {showDebug && debug && (
                  <div className="mt-3 space-y-3">
                    <p className="text-[11px] text-muted">{debug.note}</p>
                    {debug.sequence_url && (
                      <div>
                        <div className="mb-1 text-[10px] uppercase text-muted">Temporal sequence (lower-face)</div>
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={debug.sequence_url} alt="temporal sequence" className="w-full rounded border border-border" />
                      </div>
                    )}
                    <div className="grid grid-cols-4 gap-2">
                      {debug.frames.map((f, i) => (
                        <div key={i} className="space-y-1">
                          {f.original_url && (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={f.original_url} alt="orig" className="w-full rounded border border-border" title={`t=${f.timestamp}s`} />
                          )}
                          <div className="flex gap-1">
                            {f.lower_face_url && (
                              // eslint-disable-next-line @next/next/no-img-element
                              <img src={f.lower_face_url} alt="lower" className="w-1/2 rounded border border-border" title="lower-face (model input)" />
                            )}
                            {f.mouth_url && (
                              // eslint-disable-next-line @next/next/no-img-element
                              <img src={f.mouth_url} alt="mouth" className="w-1/2 rounded border border-border" title="mouth crop" />
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                    {!debug.available && <p className="text-xs text-warn">{debug.note}</p>}
                  </div>
                )}
              </div>

              {/* Developer-only evaluation (§20–§22) */}
              {devMode && (
                <div className="rounded-lg border border-border bg-panel p-4">
                  <h3 className="text-sm font-semibold">Evaluation (developer)</h3>
                  <p className="mt-1 text-[11px] text-muted">
                    Paste a known ground-truth transcript to score WER/CER. Not shown to end users.
                  </p>
                  <textarea
                    value={evalGt}
                    onChange={(e) => setEvalGt(e.target.value)}
                    placeholder="Ground-truth transcript…"
                    className="mt-2 h-20 w-full rounded border border-border bg-panel2 p-2 text-xs"
                  />
                  <button
                    onClick={runEvaluation}
                    disabled={evaluating || !evalGt.trim()}
                    className="focus-ring mt-2 rounded-lg border border-accent px-3 py-1.5 text-xs text-accent disabled:opacity-50"
                  >
                    {evaluating ? "Scoring…" : "Run evaluation"}
                  </button>
                  {evalResult && evalResult.wer != null && (
                    <div className="mt-3 space-y-1 text-xs">
                      <div className="text-muted">Prediction: <span className="text-fg">{evalResult.prediction}</span></div>
                      <div className="flex flex-wrap gap-3">
                        <span>WER <strong>{(evalResult.wer * 100).toFixed(1)}%</strong></span>
                        <span>CER <strong>{((evalResult.cer ?? 0) * 100).toFixed(1)}%</strong></span>
                        <span>S {evalResult.substitutions} · D {evalResult.deletions} · I {evalResult.insertions}</span>
                        {evalResult.average_confidence != null && (
                          <span>conf {(evalResult.average_confidence * 100).toFixed(0)}%</span>
                        )}
                      </div>
                    </div>
                  )}
                  {evalResult && evalResult.wer == null && (
                    <p className="mt-2 text-xs text-warn">{evalResult.note}</p>
                  )}
                </div>
              )}

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
                          <span className="text-muted">{fmt(g.start)}–{fmt(g.end)}</span>
                          <span>{g.direction}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : (
                  gaze && <p className="mt-2 text-sm text-muted">No gaze data.</p>
                )}
              </div>

              {/* Exports */}
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

function QRow({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt className="text-muted">{label}</dt>
      <dd className="text-right font-medium">{value}</dd>
    </>
  );
}

function SegmentRow({ s, onSeek }: { s: TranscriptSegment; onSeek: () => void }) {
  const isNoSpeech = s.text === NO_SPEECH;
  const activity = s.speaking_activity;
  return (
    <li>
      <button onClick={onSeek} className="focus-ring block w-full rounded p-2 text-left hover:bg-panel2">
        <div className="flex justify-between text-xs text-muted">
          <span>{fmt(s.start_time)}–{fmt(s.end_time)}</span>
          {!isNoSpeech && (
            <span className={confidenceClass(confidenceLevel(s.confidence, s.uncertain))}>
              {confidenceLevel(s.confidence, s.uncertain)} · {(s.confidence * 100).toFixed(0)}%
              {s.visual_quality != null && ` · vis ${s.visual_quality.toFixed(0)}%`}
            </span>
          )}
        </div>
        <div className={isNoSpeech ? "text-muted italic" : s.uncertain ? "confidence-low text-warn" : ""}>
          {isNoSpeech ? "No speech evidence (mouth not moving)" : s.text}
        </div>
        <div className="mt-1 flex flex-wrap gap-2 text-[10px] text-muted">
          {activity && <span className="rounded bg-panel2 px-1.5 py-0.5">{activity.replace("_", " ").toLowerCase()}</span>}
          {s.frame_start != null && s.frame_end != null && (
            <span>frames {s.frame_start}–{s.frame_end}</span>
          )}
          {s.window_index != null && <span>window {s.window_index}</span>}
        </div>
        {!isNoSpeech && s.alternatives && s.alternatives.length > 0 && (
          <div className="mt-1 text-[11px] text-muted">
            alt:{" "}
            {s.alternatives
              .slice(0, 3)
              .map((a) => `${a.text} (${(a.confidence * 100).toFixed(0)}%)`)
              .join("  ·  ")}
          </div>
        )}
      </button>
    </li>
  );
}

function fmt(t: number): string {
  const m = Math.floor(t / 60);
  const s = (t % 60).toFixed(1);
  return `${m}:${s.padStart(4, "0")}`;
}
