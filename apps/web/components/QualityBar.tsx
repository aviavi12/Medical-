export function QualityBar({ label, value, max = 100, suffix = "" }: {
  label: string;
  value: number;
  max?: number;
  suffix?: string;
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const tone = pct >= 75 ? "bg-good" : pct >= 50 ? "bg-warn" : "bg-bad";
  return (
    <div>
      <div className="flex justify-between text-xs text-muted">
        <span>{label}</span>
        <span>{value.toFixed(0)}{suffix}</span>
      </div>
      <div className="mt-1 h-2 w-full overflow-hidden rounded bg-panel2">
        <div className={`h-full ${tone}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
