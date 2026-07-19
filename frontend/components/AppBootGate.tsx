"use client";

import { useEffect, useState } from "react";
import { BrandMark } from "./BrandMark";

export function AppBootGate({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const timer = window.setTimeout(() => setReady(true), 1200);
    return () => window.clearTimeout(timer);
  }, []);
  if (ready) return <>{children}</>;
  return <main className="boot-screen"><div className="boot-card"><BrandMark size={76} /><div className="heartbeat-line" aria-hidden="true"><span /></div><p className="boot-kicker">VERIDEX EVIDENCE WORKSPACE</p><h1>Preparing your coverage view</h1><p>Loading live regional evidence and trust signals…</p></div></main>;
}
