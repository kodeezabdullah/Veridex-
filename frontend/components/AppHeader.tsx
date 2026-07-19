import Link from "next/link";

export function AppHeader({ section }: { section?: string }) {
  return (
    <header className="app-header">
      <Link href="/" className="brand" aria-label="Veridex home"><span className="brand-mark" aria-hidden="true">V</span><span>Veridex</span></Link>
      {section && <span className="app-section">/ {section}</span>}
      <nav aria-label="Primary navigation">
        <Link href="/">Coverage map</Link>
        <Link href="/scenarios">Scenarios</Link>
      </nav>
    </header>
  );
}
