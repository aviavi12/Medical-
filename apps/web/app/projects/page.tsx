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
                <div className="flex items-center justify-between">
                  <span className="font-medium">{v.filename}</span>
                  <span className="text-xs text-muted">{v.status}</span>
                </div>
                <div className="mt-1 text-sm text-muted">
                  {v.metadata.width}×{v.metadata.height}
                  {v.metadata.duration ? ` · ${v.metadata.duration.toFixed(1)}s` : ""}
                  {v.metadata.has_audio ? " · has audio" : " · no audio"}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
}
