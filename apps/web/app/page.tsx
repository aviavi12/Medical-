"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { TopBar } from "@/components/TopBar";
import { api } from "@/lib/api";

const MAX_MB = 2048; // matches backend max_upload_size_mb
const MAX_MINUTES = 5;
const ACCEPT = ".mp4,.mov,.webm,.m4v";
const ALLOWED_EXT = ["mp4", "mov", "webm", "m4v"];

function validateFile(file: File): string | null {
  const ext = (file.name.split(".").pop() || "").toLowerCase();
  const looksVideo = file.type.startsWith("video/") || ALLOWED_EXT.includes(ext);
  if (!looksVideo || !ALLOWED_EXT.includes(ext)) {
    return `Unsupported file type. Please upload a video: ${ALLOWED_EXT.map((e) => e.toUpperCase()).join(", ")}.`;
  }
  if (file.size > MAX_MB * 1024 * 1024) {
    return `This file is ${(file.size / (1024 * 1024 * 1024)).toFixed(1)} GB. The maximum is ${MAX_MB / 1024} GB.`;
  }
  return null;
}

export default function LandingPage() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);

  async function onFile(file: File) {
    const problem = validateFile(file);
    if (problem) {
      setError(problem);
      return;
    }
    setBusy(true);
    setError(null);
    setProgress(0);
    setFileName(file.name);
    try {
      const video = await api.uploadVideo(file, setProgress);
      router.push(`/projects/${video.id}`);
    } catch (e) {
      // Full detail is preserved for developers; users get a readable message.
      // eslint-disable-next-line no-console
      console.error("[LipSight] upload failed", e);
      setError(e instanceof Error ? e.message : "Upload failed. Please try again.");
      setBusy(false);
      setFileName(null);
    }
    // On success we navigate away, so no need to reset busy.
  }

  return (
    <div className="min-h-screen">
      <TopBar />
      <main className="mx-auto max-w-3xl px-6 py-16">
        <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-accent">
          Visual Speech Analysis
        </div>
        <h1 className="mt-2 text-4xl font-bold tracking-tight">
          Lip<span className="text-accent">Sight</span>
        </h1>
        <p className="mt-3 max-w-2xl text-lg text-muted">
          Upload a video of someone speaking to analyze visible speech from mouth movements —
          with a transcription estimate, confidence, visual quality and gaze evidence.
        </p>

        {/* Upload / drop zone */}
        <div
          role="button"
          tabIndex={0}
          aria-label="Upload a video by dropping a file here or pressing Enter to browse"
          aria-busy={busy}
          className={`focus-ring mt-8 rounded-xl border-2 border-dashed p-10 text-center transition ${
            dragActive ? "border-accent bg-panel2" : "border-border bg-panel"
          } ${busy ? "opacity-90" : "cursor-pointer"}`}
          onClick={() => !busy && inputRef.current?.click()}
          onKeyDown={(e) => {
            if (!busy && (e.key === "Enter" || e.key === " ")) {
              e.preventDefault();
              inputRef.current?.click();
            }
          }}
          onDragOver={(e) => {
            e.preventDefault();
            if (!busy) setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragActive(false);
            if (busy) return;
            const f = e.dataTransfer.files?.[0];
            if (f) onFile(f);
          }}
        >
          {busy ? (
            <div aria-live="polite">
              <p className="font-medium text-white">Uploading{fileName ? ` “${fileName}”` : ""}…</p>
              <div className="mx-auto mt-4 h-2 w-full max-w-md overflow-hidden rounded-full bg-panel2">
                <div
                  className="h-full rounded-full bg-accent transition-all"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <p className="mt-2 text-sm text-muted">{progress}%</p>
            </div>
          ) : (
            <>
              <p className="text-2xl" aria-hidden>
                ⬆️
              </p>
              <p className="mt-2 font-medium text-white">Drag &amp; drop a video here</p>
              <p className="text-sm text-muted">or</p>
              <button
                type="button"
                className="focus-ring mt-3 rounded-lg bg-accent px-5 py-2.5 font-medium text-black"
                onClick={(e) => {
                  e.stopPropagation();
                  inputRef.current?.click();
                }}
              >
                Analyze a video
              </button>
              <p className="mt-4 text-xs text-muted">
                {ALLOWED_EXT.map((x) => x.toUpperCase()).join(" · ")} · up to {MAX_MB / 1024} GB ·{" "}
                {MAX_MINUTES} min max
              </p>
            </>
          )}
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onFile(f);
              e.target.value = ""; // allow re-selecting the same file after an error
            }}
          />
        </div>

        {error && (
          <div
            role="alert"
            aria-live="assertive"
            className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-bad bg-panel2 p-3 text-sm text-bad"
          >
            <span>⛔ {error}</span>
            <button
              type="button"
              onClick={() => {
                setError(null);
                inputRef.current?.click();
              }}
              className="focus-ring rounded-lg border border-bad px-3 py-1.5 text-xs font-medium hover:bg-bad hover:text-black"
            >
              Choose another file
            </button>
          </div>
        )}

        {/* How it works */}
        <section className="mt-12">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">How it works</h2>
          <ol className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[
              ["1", "Upload video", "Add a clip of a person speaking on camera."],
              ["2", "Select a person", "LipSight detects everyone; you pick who to analyze."],
              ["3", "Analyze speech", "It reconstructs speech from visible mouth movement — visual only."],
              ["4", "Review results", "See the transcript with confidence, quality and evidence."],
            ].map(([n, title, body]) => (
              <li key={n} className="rounded-xl border border-border bg-panel p-4">
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-accent text-sm font-semibold text-black">
                  {n}
                </div>
                <div className="mt-2 font-medium text-white">{title}</div>
                <div className="mt-1 text-sm text-muted">{body}</div>
              </li>
            ))}
          </ol>
        </section>

        <div className="mt-8 grid grid-cols-1 gap-4 text-sm text-muted sm:grid-cols-3">
          <Info label="Supported">MP4 · MOV · WebM</Info>
          <Info label="Recommended">720p+, front-facing</Info>
          <Info label="Maximum">{MAX_MINUTES} minutes</Info>
        </div>

        <p className="mt-8 max-w-2xl text-sm text-muted">
          LipSight generates an AI transcription estimate from visible mouth movement. It is not a
          medical or diagnostic tool, and it does not guarantee that every spoken word is captured
          correctly — confidence varies with video quality, mouth visibility and speaking
          conditions. See the{" "}
          <Link href="/limitations" className="text-accent underline">
            limitations
          </Link>{" "}
          page.
        </p>

        <p className="mt-6 text-sm">
          <Link href="/projects" className="text-accent underline">
            View your previous analyses →
          </Link>
        </p>
      </main>
    </div>
  );
}

function Info({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-panel p-4">
      <div className="text-xs uppercase tracking-wide text-muted">{label}</div>
      <div className="mt-1 text-white">{children}</div>
    </div>
  );
}
