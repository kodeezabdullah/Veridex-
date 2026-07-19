import { AppHeader } from "@/components/AppHeader";
import { ScenarioWorkspace } from "@/components/ScenarioWorkspace";
import { WorkspaceRail } from "@/components/WorkspaceRail";

export default function ScenariosPage() { return <div className="page-shell-with-rail"><WorkspaceRail /><main className="page-content"><AppHeader section="Scenarios" /><ScenarioWorkspace /></main></div>; }
