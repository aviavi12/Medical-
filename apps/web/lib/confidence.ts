// Confidence levels (Phase 12): distinguish HIGH / MEDIUM / LOW / INSUFFICIENT.
export type ConfidenceLevel = "HIGH" | "MEDIUM" | "LOW" | "INSUFFICIENT";

export function confidenceLevel(confidence: number, uncertain: boolean): ConfidenceLevel {
  if (uncertain) return "INSUFFICIENT";
  if (confidence >= 0.7) return "HIGH";
  if (confidence >= 0.4) return "MEDIUM";
  return "LOW";
}

export function confidenceClass(level: ConfidenceLevel): string {
  switch (level) {
    case "HIGH":
      return "text-good";
    case "MEDIUM":
      return "text-warn";
    default:
      return "text-bad";
  }
}
