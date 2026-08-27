import Link from "next/link";

export function TopBar({ status }: { status?: string }) {
  return (
    <header className="flex items-center justify-between border-b border-border bg-panel px-5 py-3">
      <div className="flex items-center gap-3">
        <Link href="/" className="text-lg font-semibold tracking-tight">
          🔎 Lip<span className="text-accent">Sight</span>
        </Link>
        <nav className="ml-4 hidden gap-4 text-sm text-muted md:flex">
          <Link href="/projects" className="hover:text-white">Projects</Link>
          <Link href="/settings" className="hover:text-white">Settings</Link>
          <Link href="/limitations" className="hover:text-white">Limitations</Link>
        </nav>
      </div>
      <div className="flex items-center gap-3 text-sm">
        {status && (
          <span className="rounded-full border border-border bg-panel2 px-3 py-1 text-muted">
            {status}
          </span>
        )}
      </div>
    </header>
  );
}
