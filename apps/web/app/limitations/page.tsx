import { TopBar } from "@/components/TopBar";

const POINTS = [
  ["Lip reading is probabilistic.", "The same visible mouth movement can map to multiple sounds or words. Visual speech recognition is an inference, never guaranteed truth."],
  ["Confidence is always shown.", "Low-confidence output is marked [uncertain]; multiple candidate hypotheses may be shown instead of one confident guess."],
  ["Gaze is approximate.", "Head direction is not the same as eye gaze. Gaze toward another person is 'possible / estimated', never certainty about intent."],
  ["Face quality affects accuracy.", "Small, blurred, occluded, side-facing, or poorly lit faces reduce accuracy. When evidence is insufficient, the system says so and does not run the model."],
  ["Video resolution affects accuracy.", "Higher resolution (720p+) with a clearly visible face is strongly recommended. Upscaling does not create information that was not captured."],
  ["Multiple people create ambiguity.", "Overlapping or crossing people can reduce tracking and association confidence."],
  ["Synthetic speech is not the original audio.", "Generated audio uses a generic voice and never clones a real person's voice."],
  ["The system does not read minds.", "It infers nothing about a person's thoughts, intentions, emotions, or protected personal attributes."],
];

export default function LimitationsPage() {
  return (
    <div className="min-h-screen">
      <TopBar />
      <main className="mx-auto max-w-3xl px-6 py-10">
        <h1 className="text-2xl font-semibold">Product limitations</h1>
        <p className="mt-2 text-muted">
          SilentSpeak Lab is for legitimate video analysis and research. Please read these
          limitations before interpreting any result.
        </p>
        <div className="mt-6 space-y-4">
          {POINTS.map(([title, body]) => (
            <div key={title} className="rounded-lg border border-border bg-panel p-4">
              <h2 className="font-semibold">{title}</h2>
              <p className="mt-1 text-sm text-muted">{body}</p>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
