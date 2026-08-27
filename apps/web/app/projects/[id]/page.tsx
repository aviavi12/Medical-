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

// Terminal states of the coarse-scan job (see apps/api/services/pipeline.py).
const SCAN_DONE = "READY_FOR_SELECTION";
const SCAN_FAILED = "FAILED";
const POLL_INTERVAL_MS = 1500;
const POLL_TIMEOUT_MS = 4 * 60 * 1000; // hard cap so polling can never run forever
// In-progress coarse-scan job states (see apps/api/services/pipeline.py).
const SCAN_ACTIVE = ["QUEUED", "DETECTING_FACES", "DETECTING_PEOPLE", "QUALITY_ANALYSIS"];

const STEPS = ["Upload", "Detect people", "Select person", "Analyze speech", "Results"];

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

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

function Spinner() {
  return (
    <span
      className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
      aria-hidden
    />
  );
}

function Stepper({ current }: { current: number }) {
  return (
    <ol className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs" aria-label="progress">
      {STEPS.map((label, i) => {
        const n = i + 1;
        const done = n < current;
        const active = n === current;
        return (
          <li key={label} className="flex items-center gap-2">
            <span
              className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-semibold ${
                done
                  ? "bg-good text-black"
                  : active
                    ? "bg-accent text-black"
                    : "border border-border text-muted"
              }`}
            >
              {done ? "✓" : n}
            </span>
            <span className={active ? "font-medium text-white" : done ? "text-muted" : "text-muted"}>
              {label}
            </span>
            {n < STEPS.length && <span className="mx-1 text-border">→</span>}
          </li>
        );
      })}
    </ol>
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
  const [scanning, setScanning] = useState(false);
  const [analyzingPerson, setAnalyzingPerson] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [personError, setPersonError] = useState<string | null>(null);
  const [models, setModels] = useState<ModelsInfo | null>(null);

  // Developer tools (hidden from normal users).
  const [debug, setDebug] = useState<DebugCrops | null>(null);
  const [showDebug, setShowDebug] = useState(false);
  const [devMode, setDevMode] = useState(false);
  const [evalGt, setEvalGt] = useState("");
  const [evalResult, setEvalResult] = useState<PersonEvalResult | null>(null);
  const [evaluating, setEvaluating] = useState(false);
  const [evalError, setEvalError] = useState<string | null>(null);

  // Lifecycle guards: stop state updates / polling after unmount (§6, §20).
  const mountedRef = useRef(true);
  const pollingRef = useRef(false);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const refreshPeople = useCallback(async () => {
    const r = await api.listPeople(videoId);
    if (!mountedRef.current) return r.people;
    setPeople(r.people);
    setStatus(r.status);
    return r.people;
  }, [videoId]);

  useEffect(() => {
    api.getVideo(videoId).then((v) => mountedRef.current && setVideo(v)).catch((e) => setError(e.message));
    api.models().then((m) => mountedRef.current && setModels(m)).catch(() => undefined);
    refreshPeople().catch(() => undefined);
  }, [videoId, refreshPeople]);

  // ── Centralized coarse-scan polling (single source of truth, §9) ──────────
  // Assumes a scan job is running (freshly started, or already in progress on a
  // page refresh). Polls status until the job ends, times out, or unmounts.
  const pollScan = useCallback(async () => {
    if (pollingRef.current) return; // never poll twice at once
    pollingRef.current = true;
    setScanning(true);
    setError(null);
    const deadline = Date.now() + POLL_TIMEOUT_MS;
    try {
      while (Date.now() < deadline) {
        if (!mountedRef.current) return;
        const s = await api.status(videoId);
        if (!mountedRef.current) return;
        setStatus(s.status);
        if (s.status === SCAN_DONE) {
          const found = await refreshPeople();
          if (mountedRef.current && found.length === 0) {
            setError("No people were detected in this video. Try a clearer, more front-facing clip.");
          }
          return;
        }
        if (s.status === SCAN_FAILED) {
          throw new Error(s.error || "People detection failed. Please try a clearer video.");
        }
        await sleep(POLL_INTERVAL_MS);
      }
      throw new Error("Detection is taking longer than expected. Please try again.");
    } catch (e) {
      if (mountedRef.current) setError(humanError(e, "People detection failed. Please try again."));
    } finally {
      pollingRef.current = false;
      if (mountedRef.current) setScanning(false);
    }
  }, [videoId, refreshPeople]);

  // ── Step 2: detect people (POST /analyze is async → poll status) ──────────
  async function detectPeople() {
    if (scanning || pollingRef.current) return; // block double-click / double-poll
    setScanning(true); // close the click→poll gap so the button can't re-fire
    setError(null);
    try {
      await api.analyzeVideo(videoId); // returns 202 immediately; work runs in background
    } catch (e) {
      if (mountedRef.current) {
        setError(humanError(e, "Could not start analysis. Please try again."));
        setScanning(false);
      }
      return;
    }
    await pollScan();
  }

  // Resume polling if the user refreshes the page while a scan is mid-flight (§9),
  // so we never show the "Detect people" CTA or a premature empty gallery for a
  // job that is actually still running.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const s = await api.status(videoId);
        if (cancelled || !mountedRef.current) return;
        // Only resume when a real scan JOB is in flight. A freshly-uploaded video
        // reports status "QUEUED" with no job_id yet — that is NOT a running scan,
        // so we must show the "Analyze video" CTA, not a spinner.
        if (s.job_id && SCAN_ACTIVE.includes(s.status)) {
          setStatus(s.status);
          pollScan();
        }
      } catch {
        /* no job yet — expected on a fresh project */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [videoId, pollScan]);

  // ── Step 3: select a person ───────────────────────────────────────────────
  async function selectPerson(p: Person) {
    setSelected(p);
    setTranscript(null);
    setGaze(null);
    setPersonError(null);
    setDebug(null);
    setShowDebug(false);
    setEvalResult(null);
    // Show any prior transcript for this person (so re-selecting is instant).
    try {
      const t = await api.transcript(videoId, p.id);
      if (mountedRef.current && t.segments.length) {
        setTranscript(t);
        setGaze(await api.gaze(videoId, p.id).catch(() => null));
      }
    } catch {
      /* no prior transcript — expected */
    }
  }

  // ── Step 4: analyze speech (synchronous on the backend) ───────────────────
  async function analyzeSpeech() {
    if (!selected || analyzingPerson) return; // block double-click
    const override = selected.status === "INSUFFICIENT";
    setAnalyzingPerson(true);
    setPersonError(null);
    setTranscript(null);
    try {
      const res = await api.analyzePerson(videoId, selected.id, override);
      if (!mountedRef.current) return;
      if (res.state === "REAL_RESULT") {
        setTranscript(await api.transcript(videoId, selected.id));
        setGaze(await api.gaze(videoId, selected.id).catch(() => null));
      } else {
        // Honest, specific reason — never a bare "Analysis failed".
        setPersonError(res.detail || `No transcript produced (${res.state}).`);
        setTranscript(await api.transcript(videoId, selected.id).catch(() => null));
      }
    } catch (e) {
      if (mountedRef.current) setPersonError(humanError(e, "Speech analysis could not complete. Please try again."));
    } finally {
      if (mountedRef.current) setAnalyzingPerson(false);
    }
  }

  // ── Step 5 → reset: analyze another person (same video) ───────────────────
  function analyzeAnotherPerson() {
    setSelected(null);
    setTranscript(null);
    setGaze(null);
    setPersonError(null);
    setDebug(null);
    setShowDebug(false);
    setEvalResult(null);
    document.getElementById("people-gallery")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function loadDebug() {
    if (!selected) return;
    setShowDebug(true);
    try {
      const d = await api.debugCrops(videoId, selected.id, 4);
      if (mountedRef.current) setDebug(d);
    } catch (e) {
      if (mountedRef.current)
        setDebug({
          video_id: videoId, person_id: selected.id, available: false,
          note: humanError(e, "Could not build debug crops."),
          crop_mode: null, frames: [], sequence_url: null,
        });
    }
  }

  async function runEvaluation() {
    if (!selected || !evalGt.trim() || evaluating) return;
    setEvaluating(true);
    setEvalError(null);
    try {
      const r = await api.evaluatePerson(videoId, selected.id, evalGt, false);
      if (mountedRef.current) setEvalResult(r);
    } catch (e) {
      if (mountedRef.current) setEvalError(humanError(e, "Evaluation could not run. Please try again."));
    } finally {
      if (mountedRef.current) setEvaluating(false);
    }
  }

  function seek(t: number) {
    if (videoRef.current) {
      videoRef.current.currentTime = t;
      videoRef.current.play().catch(() => undefined);
    }
  }

  // Keyboard shortcuts for the player (ignored while typing).
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

  const hasPeople = people.length > 0;
  const hasResults = !!transcript && transcript.segments.length > 0;
  const currentStep = scanning || !hasPeople ? 2 : !selected ? 3 : !hasResults ? 4 : 5;

  return (
    <div className="min-h-screen">
      <TopBar status={status} />
      <main className="mx-auto max-w-5xl space-y-5 px-5 py-6">
        {/* Progress stepper — the user always knows where they are. */}
        <div className="rounded-xl border border-border bg-panel px-4 py-3">
          <Stepper current={currentStep} />
        </div>

        {/* Video + metadata */}
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_300px]">
          <div className="overflow-hidden rounded-xl border border-border bg-black">
            {video?.media_url ? (
              <video ref={videoRef} src={video.media_url} controls className="w-full" />
            ) : (
              <div className="p-16 text-center text-muted">Loading video…</div>
            )}
          </div>
          <div className="space-y-2 text-xs">
            <span className="inline-flex rounded-full border border-good px-2 py-1 text-good">
              ✓ Visual-only mode: ACTIVE
            </span>
            {models && (
              <div className="rounded-lg border border-border bg-panel p-3 text-muted">
                <div className="text-[10px] uppercase tracking-wide">Model</div>
                <div className="mt-0.5 text-white">
                  {models.models.find((m) => m.active)?.display_name ?? models.active_model}
                </div>
                <div className="mt-0.5">
                  {models.active_open_vocabulary ? "Open-vocabulary English" : "Closed vocab (benchmark)"} ·{" "}
                  {models.device.device.toUpperCase()}
                </div>
              </div>
            )}
            {video && (
              <div className="rounded-lg border border-border bg-panel p-3 text-muted">
                <Meta k="Audio" v={video.metadata.has_audio ? "Present (ignored)" : "None"} />
                <Meta
                  k="Resolution"
                  v={`${video.metadata.width ?? "?"}×${video.metadata.height ?? "?"}${
                    video.metadata.fps ? ` · ${Math.round(video.metadata.fps)}fps` : ""
                  }`}
                />
                <Meta k="Duration" v={video.metadata.duration ? `${video.metadata.duration.toFixed(1)}s` : "—"} />
              </div>
            )}
          </div>
        </div>

        {/* ── PRIMARY ACTION CARD — changes with the current step ──────────── */}
        <ActionCard
          scanning={scanning}
          status={status}
          hasPeople={hasPeople}
          selected={selected}
          analyzingPerson={analyzingPerson}
          hasResults={hasResults}
          onDetect={detectPeople}
          onAnalyzeSpeech={analyzeSpeech}
          onAnotherPerson={analyzeAnotherPerson}
        />

        {error && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-bad bg-panel2 p-4 text-sm text-bad">
            <span>⛔ {error}</span>
            <button
              onClick={detectPeople}
              className="focus-ring rounded-lg border border-bad px-3 py-1.5 text-xs font-medium hover:bg-bad hover:text-black"
            >
              Retry
            </button>
          </div>
        )}

        {/* ── PEOPLE GALLERY ──────────────────────────────────────────────── */}
        {hasPeople && (
          <section id="people-gallery">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted">
              People detected · {people.length}
            </h2>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {people.map((p) => {
                const isSel = selected?.id === p.id;
                return (
                  <button
                    key={p.id}
                    onClick={() => selectPerson(p)}
                    aria-pressed={isSel}
                    className={`focus-ring rounded-lg border p-3 text-left transition ${
                      isSel ? "border-accent ring-1 ring-accent" : "border-border hover:border-accent"
                    } bg-panel`}
                  >
                    <div className="flex items-center gap-3">
                      {p.thumbnail_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={p.thumbnail_url} alt={p.label} className="h-14 w-14 rounded object-cover" />
                      ) : (
                        <div className="flex h-14 w-14 items-center justify-center rounded bg-panel2 text-muted">
                          {p.track_number}
                        </div>
                      )}
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{p.label}</span>
                          <StatusBadge status={p.status} />
                        </div>
                        <div className="text-xs text-muted">
                          {p.screen_time.toFixed(1)}s on screen · face ~
                          {Math.round(p.quality_report?.avg_face_width_px ?? 0)}px
                        </div>
                        <div className="mt-2 space-y-1">
                          <QualityBar label="Lip-reading readiness" value={p.lip_readiness} />
                        </div>
                      </div>
                      <span
                        className={`shrink-0 rounded-lg px-3 py-1.5 text-xs font-medium ${
                          isSel ? "bg-accent text-black" : "border border-border text-muted"
                        }`}
                      >
                        {isSel ? "Selected" : "Select"}
                      </span>
                    </div>
                    {p.reason && (
                      <p className={`mt-2 text-xs ${p.status === "INSUFFICIENT" ? "text-bad" : "text-warn"}`}>
                        {p.reason}
                      </p>
                    )}
                  </button>
                );
              })}
            </div>
          </section>
        )}

        {/* ── SELECTED PERSON QUALITY REPORT (context for Analyze speech) ──── */}
        {selected && !hasResults && (
          <section className="rounded-xl border border-border bg-panel p-4">
            <div className="flex items-center gap-3">
              {selected.thumbnail_url && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={selected.thumbnail_url} alt={selected.label} className="h-12 w-12 rounded object-cover" />
              )}
              <div className="flex items-center gap-2 font-semibold">
                {selected.label} <StatusBadge status={selected.status} />
              </div>
            </div>
            {selected.quality_report && (
              <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-[11px] sm:grid-cols-4">
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
                {selected.quality_report.reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            ) : null}
          </section>
        )}

        {/* A genuine failure (no transcript produced) — distinct from a low-confidence
            success, and offers Retry (§5, §11). */}
        {personError && !hasResults && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-bad bg-panel2 p-4 text-sm">
            <div className="text-bad">
              <div className="font-semibold">⛔ Analysis failed</div>
              <p className="mt-1 text-muted">{personError}</p>
            </div>
            <button
              onClick={() => analyzeSpeech()}
              disabled={analyzingPerson}
              className="focus-ring rounded-lg border border-bad px-3 py-1.5 text-xs font-medium text-bad hover:bg-bad hover:text-black disabled:opacity-50"
            >
              Retry analysis
            </button>
          </div>
        )}

        {/* ── RESULTS ─────────────────────────────────────────────────────── */}
        {selected && hasResults && (
          <section className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">
                Results · {selected.label}
              </h2>
              {transcript?.model_version && (
                <span className="text-[10px] text-muted">{transcript.model_version}</span>
              )}
            </div>

            {/* 1. Analysis status + confidence/quality summary (§5, §6, §17). */}
            <ResultsSummary t={transcript!} />

            {/* Transcript */}
            <div className="rounded-xl border border-border bg-panel p-4">
              <h3 className="mb-2 text-sm font-semibold">Visual speech transcription</h3>
              {transcript && <AvailabilityNotice availability={transcript.availability} />}
              <ul className="mt-2 space-y-2">
                {transcript!.segments.map((s, i) => (
                  <SegmentRow key={i} s={s} onSeek={() => seek(s.start_time)} />
                ))}
              </ul>
            </div>

            {/* Gaze + Export side by side */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="rounded-xl border border-border bg-panel p-4">
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
                  <p className="mt-2 text-sm text-muted">Not available.</p>
                )}
              </div>

              <div className="rounded-xl border border-border bg-panel p-4">
                <h3 className="mb-2 text-sm font-semibold">Export</h3>
                <div className="flex flex-wrap gap-2">
                  {["srt", "txt", "json", "report"].map((fmtName) => (
                    <a
                      key={fmtName}
                      href={api.exportUrl(videoId, selected.id, fmtName)}
                      className="focus-ring rounded border border-border px-3 py-1 text-xs hover:border-accent"
                    >
                      {fmtName.toUpperCase()}
                    </a>
                  ))}
                </div>
                <Link
                  href={`/projects/${videoId}/person/${selected.id}`}
                  className="mt-3 inline-block text-xs text-accent underline"
                >
                  Open detailed view →
                </Link>
              </div>
            </div>

            {/* Debug: what the model sees */}
            <div className="rounded-xl border border-border bg-panel p-4">
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

            {/* Developer-only evaluation */}
            <div className="rounded-xl border border-border bg-panel p-4">
              <label className="flex items-center gap-2 text-xs text-muted">
                <input type="checkbox" checked={devMode} onChange={(e) => setDevMode(e.target.checked)} />
                Developer tools (evaluate against a known transcript)
              </label>
              {devMode && (
                <div className="mt-3">
                  <p className="text-[11px] text-muted">
                    Paste the known ground-truth transcript to score WER/CER. Used only after inference; not shown to end users.
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
                    className="focus-ring mt-2 inline-flex items-center gap-2 rounded-lg border border-accent px-3 py-1.5 text-xs text-accent disabled:opacity-50"
                  >
                    {evaluating && <Spinner />}
                    {evaluating ? "Scoring…" : "Run evaluation"}
                  </button>
                  {evalResult && evalResult.wer != null && (
                    <div className="mt-3 space-y-1 text-xs">
                      <div className="text-muted">
                        Prediction: <span className="text-white">{evalResult.prediction}</span>
                      </div>
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
                  {evalError && <p className="mt-2 text-xs text-bad">{evalError}</p>}
                </div>
              )}
            </div>

            {/* Next-action CTAs */}
            <div className="flex flex-wrap gap-3 border-t border-border pt-4">
              {people.length > 1 && (
                <button
                  onClick={analyzeAnotherPerson}
                  className="focus-ring rounded-lg border border-border px-4 py-2 text-sm font-medium hover:border-accent"
                >
                  Analyze another person
                </button>
              )}
              <Link
                href="/"
                className="focus-ring rounded-lg bg-accent px-4 py-2 text-sm font-medium text-black"
              >
                Analyze another video
              </Link>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

// ── Primary action card ─────────────────────────────────────────────────────
function ActionCard(props: {
  scanning: boolean;
  status: string;
  hasPeople: boolean;
  selected: Person | null;
  analyzingPerson: boolean;
  hasResults: boolean;
  onDetect: () => void;
  onAnalyzeSpeech: () => void;
  onAnotherPerson: () => void;
}) {
  const { scanning, status, hasPeople, selected, analyzingPerson, hasResults } = props;

  if (scanning) {
    return (
      <Card tone="busy">
        <div className="flex items-center gap-3">
          <Spinner />
          <div>
            <div className="font-medium text-white">Analyzing video — detecting people…</div>
            <div className="text-xs text-muted">{humanStatus(status)}</div>
          </div>
        </div>
      </Card>
    );
  }

  if (!hasPeople) {
    return (
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="font-medium text-white">Step 2 — Detect people in this video</div>
            <div className="text-xs text-muted">
              We scan the whole video and list every clearly-visible person so you can pick one.
            </div>
          </div>
          <button
            onClick={props.onDetect}
            className="focus-ring rounded-lg bg-accent px-5 py-2.5 font-medium text-black"
          >
            Analyze video
          </button>
        </div>
      </Card>
    );
  }

  if (analyzingPerson) {
    return (
      <Card tone="busy">
        <div className="flex items-center gap-3">
          <Spinner />
          <div>
            <div className="font-medium text-white">Analyzing speech…</div>
            <div className="text-xs text-muted">
              Running visual speech recognition on the selected person. The first run also loads the
              model and can take up to ~2 minutes.
            </div>
          </div>
        </div>
      </Card>
    );
  }

  if (hasResults) {
    return (
      <Card tone="done">
        <div className="flex items-center gap-3">
          <span className="text-good">✓</span>
          <div className="font-medium text-white">Analysis complete — results are below.</div>
        </div>
      </Card>
    );
  }

  if (selected) {
    const insufficient = selected.status === "INSUFFICIENT";
    return (
      <Card tone={insufficient ? "warn" : "default"}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="font-medium text-white">
              Step 4 — {selected.label} selected
            </div>
            <div className="text-xs text-muted">
              {insufficient
                ? "Visual quality is low for this person — you can still try, but results may be poor."
                : "Run visual speech recognition on this person’s mouth movement."}
            </div>
          </div>
          <button
            onClick={props.onAnalyzeSpeech}
            className="focus-ring rounded-lg bg-accent px-5 py-2.5 font-medium text-black"
          >
            {insufficient ? "Analyze speech anyway" : "Analyze speech"}
          </button>
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <div className="font-medium text-white">Step 3 — Select a person below</div>
      <div className="text-xs text-muted">Pick whose visible speech you want to transcribe.</div>
    </Card>
  );
}

function Card({ children, tone = "default" }: { children: React.ReactNode; tone?: "default" | "busy" | "done" | "warn" }) {
  const border =
    tone === "busy" ? "border-accent" : tone === "done" ? "border-good" : tone === "warn" ? "border-warn" : "border-border";
  return <div className={`rounded-xl border ${border} bg-panel p-4`}>{children}</div>;
}

function Meta({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-3 py-0.5">
      <span className="text-[10px] uppercase tracking-wide">{k}</span>
      <span className="text-white">{v}</span>
    </div>
  );
}

const UNCERTAIN = "[uncertain]";

// Analysis status + confidence/quality summary. A REAL_RESULT with low confidence
// is a SUCCESS with uncertainty — never a failure (§5, §17). It never claims
// accuracy; it states the measured confidence and, when not high, how to improve it.
function ResultsSummary({ t }: { t: Transcript }) {
  const speech = t.segments.filter((s) => s.text !== NO_SPEECH);
  const withWords = speech.filter((s) => s.text && s.text !== UNCERTAIN && !s.uncertain);
  const conf = speech.length ? speech.reduce((a, s) => a + (s.confidence || 0), 0) / speech.length : 0;
  const visSegs = t.segments.filter((s) => s.visual_quality != null);
  const vis = visSegs.length
    ? visSegs.reduce((a, s) => a + (s.visual_quality || 0), 0) / visSegs.length
    : null;
  const noSpeech = withWords.length === 0;
  const level = confidenceLevel(conf, false); // HIGH / MEDIUM / LOW
  const label = noSpeech
    ? "No confident speech"
    : level === "HIGH"
      ? "High confidence"
      : level === "MEDIUM"
        ? "Moderate confidence"
        : "Low confidence";
  const labelColor = noSpeech
    ? "text-muted"
    : level === "HIGH"
      ? "text-good"
      : level === "MEDIUM"
        ? "text-warn"
        : "text-bad";

  return (
    <div className="rounded-xl border border-good bg-panel p-4">
      <div className="flex items-center gap-2">
        <span className="text-good">✓</span>
        <span className="font-semibold text-white">Analysis complete</span>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Stat label="Confidence" value={noSpeech ? "—" : `${(conf * 100).toFixed(0)}%`} />
        <Stat label="Reliability" value={label} valueClass={labelColor} />
        <Stat label="Visual quality" value={vis != null ? `${vis.toFixed(0)}%` : "—"} />
      </div>
      {noSpeech ? (
        <p className="mt-3 rounded-md border border-border bg-panel2 p-2 text-xs text-muted">
          The analysis ran successfully, but no confident speech was detected for this person —
          the mouth may not be moving in view, or the face is unclear.
        </p>
      ) : level !== "HIGH" ? (
        <p className="mt-3 rounded-md border border-warn bg-panel2 p-2 text-xs text-warn">
          Results are available, but confidence is {level === "MEDIUM" ? "moderate" : "low"}. Lip
          reading is probabilistic — for more reliable results use a clearer, closer, well-lit,
          front-facing view of the speaker.
        </p>
      ) : null}
    </div>
  );
}

function Stat({ label, value, valueClass = "text-white" }: { label: string; value: string; valueClass?: string }) {
  return (
    <div className="rounded-lg border border-border bg-panel2 p-3">
      <div className="text-[10px] uppercase tracking-wide text-muted">{label}</div>
      <div className={`mt-0.5 text-lg font-semibold ${valueClass}`}>{value}</div>
    </div>
  );
}

function QRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2">
      <dt className="text-muted">{label}</dt>
      <dd className="font-medium text-white">{value}</dd>
    </div>
  );
}

function SegmentRow({ s, onSeek }: { s: TranscriptSegment; onSeek: () => void }) {
  const isNoSpeech = s.text === NO_SPEECH;
  const activity = s.speaking_activity;
  return (
    <li>
      <button onClick={onSeek} className="focus-ring block w-full rounded p-2 text-left hover:bg-panel2">
        <div className="flex justify-between text-xs text-muted">
          <span>
            {fmt(s.start_time)}–{fmt(s.end_time)}
          </span>
          {!isNoSpeech && (
            <span className={confidenceClass(confidenceLevel(s.confidence, s.uncertain))}>
              {confidenceLevel(s.confidence, s.uncertain)} · {(s.confidence * 100).toFixed(0)}%
              {s.visual_quality != null && ` · vis ${s.visual_quality.toFixed(0)}%`}
            </span>
          )}
        </div>
        <div className={isNoSpeech ? "italic text-muted" : s.uncertain ? "confidence-low text-warn" : "text-white"}>
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

function humanStatus(status: string): string {
  const map: Record<string, string> = {
    QUEUED: "Queued…",
    DETECTING_FACES: "Detecting faces…",
    DETECTING_PEOPLE: "Detecting people…",
    QUALITY_ANALYSIS: "Scoring face quality…",
    READY_FOR_SELECTION: "Done.",
  };
  return map[status] || "Working…";
}

function humanError(e: unknown, fallback: string): string {
  // Keep the full error in the console for developers; show a human message.
  if (e instanceof Error) {
    // eslint-disable-next-line no-console
    console.error("[SilentSpeak]", e);
    // Surface backend-provided detail when it is already human-readable.
    if (e.message && !/^\d{3}$/.test(e.message) && !/failed with status/i.test(e.message)) {
      return e.message;
    }
  } else {
    // eslint-disable-next-line no-console
    console.error("[SilentSpeak]", e);
  }
  return fallback;
}

function fmt(t: number): string {
  const m = Math.floor(t / 60);
  const s = (t % 60).toFixed(1);
  return `${m}:${s.padStart(4, "0")}`;
}
