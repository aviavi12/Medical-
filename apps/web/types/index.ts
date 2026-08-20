// Transport types mirroring apps/api/schemas/dto.py.

export interface Availability {
  state: "REAL_RESULT" | "MODEL_UNAVAILABLE" | "LOW_CONFIDENCE" | "NO_SIGNAL";
  detail: string | null;
  missing: string[];
  model: Record<string, unknown> | null;
}

export interface VideoMetadata {
  duration: number | null;
  width: number | null;
  height: number | null;
  fps: number | null;
  codec: string | null;
  has_audio: boolean;
  size_bytes: number | null;
}

export interface Video {
  id: string;
  filename: string;
  status: string;
  project_id: string | null;
  metadata: VideoMetadata;
  media_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobStatus {
  video_id: string;
  job_id: string | null;
  status: string;
  stage: string | null;
  progress: number;
  frames_total: number | null;
  frames_done: number | null;
  device: string | null;
  elapsed_seconds: number | null;
  eta_seconds: number | null;
  error: string | null;
}

export interface Person {
  id: string;
  track_number: number;
  label: string;
  screen_time: number;
  visibility: number;
  face_quality: number;
  lip_readiness: number;
  average_detection_confidence: number;
  first_timestamp: number | null;
  last_timestamp: number | null;
  thumbnail_url: string | null;
  selectable: boolean;
  reason: string | null;
}

export interface TranscriptWord {
  word: string;
  start: number;
  end: number;
  confidence: number;
}

export interface TranscriptSegment {
  start_time: number;
  end_time: number;
  text: string;
  confidence: number;
  raw_text: string;
  processed_text: string;
  uncertain: boolean;
  words: TranscriptWord[];
  alternatives: { text: string; confidence: number }[];
}

export interface Transcript {
  video_id: string;
  person_id: string;
  availability: Availability;
  model_version: string | null;
  segments: TranscriptSegment[];
}

export interface GazeSegment {
  start: number;
  end: number;
  direction: string;
  confidence: number;
  target_person_id: string | null;
  target_confidence: number;
}

export interface GazeTimeline {
  video_id: string;
  person_id: string;
  availability: Availability;
  segments: GazeSegment[];
}

export interface PersonAnalysisResult {
  video_id: string;
  person_id: string;
  state: string;
  detail: string | null;
  segments: number;
  gaze: number;
  landmarks_available: boolean;
  lipreading_available: boolean;
}
