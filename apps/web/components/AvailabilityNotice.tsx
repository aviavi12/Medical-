import type { Availability } from "@/types";

const LABELS: Record<string, { title: string; className: string; icon: string }> = {
  REAL_RESULT: { title: "Real model result", className: "border-good text-good", icon: "✓" },
  MODEL_UNAVAILABLE: { title: "MODEL UNAVAILABLE", className: "border-bad text-bad", icon: "⛔" },
  LOW_CONFIDENCE: { title: "Low confidence", className: "border-warn text-warn", icon: "≈" },
  NO_SIGNAL: { title: "No usable visual signal", className: "border-warn text-warn", icon: "∅" },
};

export function AvailabilityNotice({ availability }: { availability: Availability }) {
  if (availability.state === "REAL_RESULT") return null;
  const meta = LABELS[availability.state] || LABELS.MODEL_UNAVAILABLE;
  return (
    <div className={`rounded-md border ${meta.className} bg-panel2 p-4 text-sm`}>
      <div className="font-semibold">
        {meta.icon} {meta.title}
      </div>
      {availability.detail && <p className="mt-1 text-muted">{availability.detail}</p>}
      {availability.missing.length > 0 && (
        <div className="mt-2">
          <span className="text-muted">Missing: </span>
          {availability.missing.map((m) => (
            <code key={m} className="mr-1 rounded bg-black/40 px-1 py-0.5 text-xs">
              {m}
            </code>
          ))}
        </div>
      )}
    </div>
  );
}
