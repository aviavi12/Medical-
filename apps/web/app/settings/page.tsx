"use client";

import { useEffect, useState } from "react";

import { TopBar } from "@/components/TopBar";
import { api } from "@/lib/api";

export default function SettingsPage() {
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.health().then(setHealth).catch((e) => setError(e.message));
  }, []);

  const device = (health?.device as Record<string, unknown>) || {};

  return (
    <div className="min-h-screen">
      <TopBar />
      <main className="mx-auto max-w-3xl px-6 py-8">
        <h1 className="text-2xl font-semibold">System &amp; model settings</h1>
        <p className="mt-1 text-sm text-muted">
          Model back-ends are configured via environment variables (see <code>.env.example</code>).
          Missing models are reported as <span className="text-bad">MODEL UNAVAILABLE</span> rather than faked.
        </p>

        {error && <p className="mt-4 text-bad">⛔ {error}</p>}
        {health && (
          <div className="mt-6 space-y-2 rounded-lg border border-border bg-panel p-4 text-sm">
            <Row k="App" v={`${health.app} v${health.version}`} />
            <Row k="Environment" v={String(health.env)} />
            <Row k="Database" v={String(health.database)} />
            <Row k="FFmpeg" v={health.ffmpeg ? "installed" : "missing"} />
            <Row k="Processing device" v={String(device.device)} />
            <Row k="Torch available" v={device.torch ? "yes" : "no"} />
          </div>
        )}

        <div className="mt-6 rounded-lg border border-border bg-panel p-4 text-sm">
          <h2 className="font-semibold">Configured models</h2>
          <ul className="mt-2 space-y-1 text-muted">
            <li>Person detector: YOLO (configurable IMG_SIZE)</li>
            <li>Face detector: MediaPipe / YOLO-face (benchmark-selected)</li>
            <li>Tracker: ByteTrack / BoT-SORT (IoU fallback)</li>
            <li>Lip reading: AV-HuBERT (English VSR, non-commercial license)</li>
            <li>TTS: Piper (generic voice)</li>
          </ul>
        </div>
      </main>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted">{k}</span>
      <span>{v}</span>
    </div>
  );
}
