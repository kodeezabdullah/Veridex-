import Link from "next/link";
import { BarChart3, ClipboardList, Home, Map, MapPinned } from "lucide-react";
import { BrandMark } from "./BrandMark";
const items = [{ href: "/", label: "Overview", icon: Home }, { href: "/map?capability=ICU", label: "Map view", icon: Map }, { href: "/analytics", label: "Analytics", icon: BarChart3 }, { href: "/scenarios", label: "Scenarios", icon: ClipboardList }];
export function WorkspaceRail() {
  return <aside className="workspace-rail" aria-label="Primary navigation"><Link href="/" className="workspace-rail-brand" aria-label="Veridex overview"><BrandMark size={30} /><span className="workspace-rail-name">Veridex</span></Link><nav className="workspace-rail-nav">{items.map(({ href, label, icon: Icon }) => <Link key={label} href={href} className="workspace-rail-item"><Icon size={17} strokeWidth={1.8} /><span>{label}</span></Link>)}</nav><div className="workspace-rail-foot"><MapPinned size={16} /><span>India ADM2</span></div></aside>;
}
