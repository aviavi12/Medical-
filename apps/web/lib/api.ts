import type {
  DebugCrops,
  GazeTimeline,
  JobStatus,
  Person,
  PersonAnalysisResult,
  PersonEvalResult,
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

  // Uploads via XHR so we can report real upload progress (fetch cannot).
  uploadVideo(file: File, onProgress?: (pct: number) => void): Promise<Video> {
    return new Promise<Video>((resolve, reject) => {
      const form = new FormData();
      form.append("file", file);
      const xhr = new XMLHttpRequest();
      xhr.open("POST", "/api/videos");
      if (onProgress) {
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
        };
      }
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(JSON.parse(xhr.responseText) as Video);
          } catch {
            reject(new Error("Upload succeeded but the response could not be read."));
          }
        } else {
          let detail = "Upload failed. Please try again.";
          try {
            const body = JSON.parse(xhr.responseText);
            detail = body.detail || body.error || detail;
          } catch {
            /* keep default */
          }
          reject(new Error(detail));
        }
      };
      xhr.onerror = () => reject(new Error("Network error during upload. Check your connection and try again."));
      xhr.ontimeout = () => reject(new Error("The upload timed out. Please try again."));
      xhr.send(form);
    });
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

  debugCrops: (videoId: string, personId: string, samples = 4) =>
    req<DebugCrops>(`/api/videos/${videoId}/people/${personId}/debug?samples=${samples}`),

  evaluatePerson: (videoId: string, personId: string, groundTruth: string, useProcessed = false) =>
    req<PersonEvalResult>(`/api/videos/${videoId}/people/${personId}/evaluate`, {
      method: "POST",
      body: JSON.stringify({ ground_truth: groundTruth, use_processed: useProcessed }),
    }),

  gaze: (videoId: string, personId: string) =>
    req<GazeTimeline>(`/api/videos/${videoId}/people/${personId}/gaze`),

  tts: (videoId: string, personId: string, voice = "generic") =>
    req<{ url: string | null; label: string; availability: { state: string; detail: string | null } }>(
      `/api/videos/${videoId}/people/${personId}/tts`,
      { method: "POST", body: JSON.stringify({ voice }) },
    ),

  exportUrl: (videoId: string, personId: string, fmt: string) =>
    `/api/videos/${videoId}/people/${personId}/export/${fmt}`,

  models: () =>
    req<{
      active_model: string;
      active_open_vocabulary: boolean;
      visual_only: boolean;
      audio: string;
      device: { device: string };
      models: {
        key: string; display_name: string; status: string; open_vocabulary: boolean;
        dataset: string; vocabulary: string; license: string; installed: string;
        active: boolean; notes: string;
      }[];
    }>("/api/models"),

  evaluate: (predictions: string[], references: string[]) =>
    req<{ wer: number; cer: number; sentence_accuracy: number; n: number }>(`/api/evaluation`, {
      method: "POST",
      body: JSON.stringify({ predictions, references }),
    }),
};
