"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { TopBar } from "@/components/TopBar";
import { api } from "@/lib/api";
import type { Video } from "@/types";

export default function ProjectsPage() {
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listVideos()
      .then((r) => setVideos(r.videos))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen">
      <TopBar />
      <main className="mx-auto max-w-4xl px-6 py-10">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold">Projects</h1>
          <Link href="/" className="text-sm text-accent underline">
            + New upload
          </Link>
        </div>

        {loading && <p className="mt-6 text-muted">Loading…</p>}
        {error && <p className="mt-6 text-bad">⛔ {error}</p>}
        {!loading && videos.length === 0 && (
          <p className="mt-6 text-muted">No videos yet. Upload one to get started.</p>
        )}

        <ul className="mt-6 space-y-3">
          {videos.map((v) => (
            <li key={v.id}>
              <Link
                href={`/projects/${v.id}`}
                className="block rounded-lg border border-border bg-panel p-4 hover:border-accent"
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium">{v.filename}</span>
                  <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${statusPill(v.status)}`}>
                    {statusLabel(v.status)}
                  </span>
                </div>
                <div className="mt-1 text-sm text-muted">
                  {v.metadata.width}×{v.metadata.height}
                  {v.metadata.duration ? ` · ${v.metadata.duration.toFixed(1)}s` : ""}
                  {v.metadata.has_audio ? " · audio ignored" : " · no audio"}
                  {v.created_at ? ` · ${fmtDate(v.created_at)}` : ""}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    QUEUED: "Uploaded",
    READY_FOR_SELECTION: "Ready to analyze",
    DETECTING_FACES: "Detecting people…",
    QUALITY_ANALYSIS: "Assessing quality…",
    FAILED: "Failed",
    COMPLETED: "Analyzed",
  };
  return map[status] || status;
}

function statusPill(status: string): string {
  if (status === "FAILED") return "border-bad text-bad";
  if (status === "READY_FOR_SELECTION" || status === "COMPLETED") return "border-good text-good";
  return "border-border text-muted";
}

function fmtDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}
