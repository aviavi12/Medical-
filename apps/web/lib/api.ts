import type {
  GazeTimeline,
  JobStatus,
  Person,
  PersonAnalysisResult,
  Transcript,
  Video,
} from "@/types";

// Requests go to same-origin /api/* which Next rewrites to the FastAPI backend.
async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || body.error || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  health: () => req<Record<string, unknown>>("/health"),

  listVideos: () => req<{ videos: Video[]; total: number }>("/api/videos"),
  getVideo: (id: string) => req<Video>(`/api/videos/${id}`),
  deleteVideo: (id: string) => req<void>(`/api/videos/${id}`, { method: "DELETE" }),

  async uploadVideo(file: File): Promise<Video> {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch("/api/videos", { method: "POST", body: form });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || body.error || "Upload failed");
    }
    return res.json();
  },

  analyzeVideo: (id: string) =>
    req<JobStatus>(`/api/videos/${id}/analyze`, { method: "POST" }),
  status: (id: string) => req<JobStatus>(`/api/videos/${id}/status`),

  listPeople: (id: string) =>
    req<{ video_id: string; people: Person[]; status: string }>(`/api/videos/${id}/people`),

  analyzePerson: (videoId: string, personId: string, overrideGates = false) =>
    req<PersonAnalysisResult>(`/api/videos/${videoId}/people/${personId}/analyze`, {
      method: "POST",
      body: JSON.stringify({ override_quality_gates: overrideGates }),
    }),

  transcript: (videoId: string, personId: string) =>
    req<Transcript>(`/api/videos/${videoId}/people/${personId}/transcript`),

  gaze: (videoId: string, personId: string) =>
    req<GazeTimeline>(`/api/videos/${videoId}/people/${personId}/gaze`),

  tts: (videoId: string, personId: string, voice = "generic") =>
    req<{ url: string | null; label: string; availability: { state: string; detail: string | null } }>(
      `/api/videos/${videoId}/people/${personId}/tts`,
      { method: "POST", body: JSON.stringify({ voice }) },
    ),

  exportUrl: (videoId: string, personId: string, fmt: string) =>
    `/api/videos/${videoId}/people/${personId}/export/${fmt}`,

  evaluate: (predictions: string[], references: string[]) =>
    req<{ wer: number; cer: number; sentence_accuracy: number; n: number }>(`/api/evaluation`, {
      method: "POST",
      body: JSON.stringify({ predictions, references }),
    }),
};
