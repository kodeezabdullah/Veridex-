import Link from "next/link";
import { SearchPlanner } from "@/components/SearchPlanner";
import { getSelectorOptions } from "@/lib/api";

export default async function Home() {
  const selectorOptions = await getSelectorOptions();

  return (
    <main className="landing-shell">
      <header className="site-header">
        <Link href="/" className="brand" aria-label="Veridex home">
          <span className="brand-mark" aria-hidden="true">V</span>
          <span>Veridex</span>
        </Link>
        <div className="header-context">
          <span>Healthcare intelligence</span>
          <span className="header-rule" />
          <span>India</span>
        </div>
        <Link className="saved-link" href="/scenarios">
          Saved scenarios <span aria-hidden="true">0</span>
        </Link>
      </header>

      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Evidence-led planning · District by district</p>
          <h1>See where care is <em>credible.</em></h1>
          <p className="hero-intro">
            Explore healthcare capabilities without hiding the uncertainty. Veridex brings every claim, confidence signal, and evidence trail into view.
          </p>
          <div className="status-key" aria-label="Coverage status preview">
            <span><i className="verified" /> Verified</span>
            <span><i className="claimed" /> Claimed only</span>
            <span><i className="gap" /> Confirmed gap</span>
            <span><i className="unknown" /> No data</span>
          </div>
        </div>

        <SearchPlanner {...selectorOptions} />
      </section>

      <footer className="landing-footer">
        <p>Built for planners who need the evidence, not a black-box answer.</p>
        <span>Coverage intelligence · Human judgment</span>
      </footer>
    </main>
  );
}
