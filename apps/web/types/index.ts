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

export type ReadinessStatus = "READY" | "WARNING" | "INSUFFICIENT";

export interface PersonQualityReport {
  status: ReadinessStatus;
  readiness_score: number;
  face_quality_score: number;
  lip_readiness_score: number;
  usable_duration: number;
  visible_ratio: number;
  avg_face_width_px: number;
  avg_mouth_visibility_pct: number;
  avg_sharpness: number;
  avg_pose_quality: number;
  tracking_stability: number;
  reasons: string[];
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
  status: ReadinessStatus;
  reason: string | null;
  quality_report: PersonQualityReport | null;
}

export interface TranscriptWord {
  word: string;
  start: number;
  end: number;
  confidence: number;
}

export type SpeakingActivity = "SPEAKING_LIKELY" | "NOT_SPEAKING" | "UNCERTAIN";

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
  visual_quality: number | null;
  speaking_activity: SpeakingActivity | null;
  frame_start: number | null;
  frame_end: number | null;
  window_index: number | null;
  person_id: string | null;
}

export interface DebugCropFrame {
  timestamp: number;
  original_url: string | null;
  face_url: string | null;
  lower_face_url: string | null;
  mouth_url: string | null;
}

export interface DebugCrops {
  video_id: string;
  person_id: string;
  available: boolean;
  note: string;
  crop_mode: string | null;
  frames: DebugCropFrame[];
  sequence_url: string | null;
}

export interface PersonEvalResult {
  video_id: string;
  person_id: string;
  enabled: boolean;
  prediction: string;
  reference: string;
  wer: number | null;
  cer: number | null;
  substitutions: number | null;
  deletions: number | null;
  insertions: number | null;
  ref_words: number | null;
  hyp_words: number | null;
  average_confidence: number | null;
  note: string;
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
