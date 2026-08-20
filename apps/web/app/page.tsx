"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { TopBar } from "@/components/TopBar";
import { api } from "@/lib/api";

export default function LandingPage() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onFile(file: File) {
    setBusy(true);
    setError(null);
    try {
      const video = await api.uploadVideo(file);
      router.push(`/projects/${video.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen">
      <TopBar />
      <main className="mx-auto max-w-3xl px-6 py-16">
        <h1 className="text-4xl font-bold tracking-tight">SilentSpeak Lab</h1>
        <p className="mt-3 text-lg text-muted">Analyze visible speech in English video.</p>

        <div
          className="mt-10 rounded-xl border border-dashed border-border bg-panel p-10 text-center"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const f = e.dataTransfer.files?.[0];
            if (f) onFile(f);
          }}
        >
          <p className="text-muted">Drag a video here, or</p>
          <button
            className="focus-ring mt-4 rounded-lg bg-accent px-5 py-2.5 font-medium text-black disabled:opacity-50"
            disabled={busy}
            onClick={() => inputRef.current?.click()}
          >
            {busy ? "Uploading…" : "Upload Video"}
          </button>
          <input
            ref={inputRef}
            type="file"
            accept="video/mp4,video/quicktime,video/webm,.mp4,.mov,.webm,.m4v"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onFile(f);
            }}
          />
          {error && <p className="mt-4 text-sm text-bad">⛔ {error}</p>}
        </div>

        <div className="mt-8 grid grid-cols-1 gap-4 text-sm text-muted sm:grid-cols-3">
          <Info label="Supported">MP4, MOV, WebM</Info>
          <Info label="Recommended">720p or higher</Info>
          <Info label="Maximum">5 minutes</Info>
        </div>

        <p className="mt-8 text-sm text-muted">
          Results depend heavily on face visibility and video quality. Lip reading is
          probabilistic — the system shows confidence and marks uncertain output. See the{" "}
          <a href="/limitations" className="text-accent underline">
            limitations
          </a>{" "}
          page.
        </p>

        <p className="mt-6 text-sm">
          <a href="/projects" className="text-accent underline">
            View existing projects →
          </a>
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
