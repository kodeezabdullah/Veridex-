import Link from "next/link";
export default function NotFound() { return <main className="not-found"><span>404</span><h1>Evidence record not found</h1><p>The requested record is not present in the current index.</p><Link className="primary-button" href="/">Return home</Link></main>; }
