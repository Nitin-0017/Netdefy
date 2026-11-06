import { useState } from 'react';
import {
  Header,
  AppArea,
  ConsoleTabKey,
  ResearchTabKey,
} from './components/Header';
import { ConsoleOverview } from './components/ConsoleOverview';
import { AnalyzeTraffic } from './components/AnalyzeTraffic';
import { DetectionHistory } from './components/DetectionHistory';
import { ThreatIntelligence } from './components/ThreatIntelligence';
import { ResearchOverview } from './components/ResearchOverview';
import { ModelComparison } from './components/ModelComparison';
import { AnomalyCalibration } from './components/AnomalyCalibration';
import { ClassificationDiagnostics } from './components/ClassificationDiagnostics';
import { HybridDecisionView } from './components/HybridDecisionView';
import { ExplainabilitySpec } from './components/ExplainabilitySpec';
import { Playground } from './components/Playground';
import { Shield, GitBranch, Database, Cpu } from 'lucide-react';

export function App() {
  const getInitialState = (): {
    area: AppArea;
    consoleTab: ConsoleTabKey;
    researchTab: ResearchTabKey;
  } => {
    try {
      const params = new URLSearchParams(window.location.search);
      const areaParam = params.get('area') as AppArea;
      const tabParam = params.get('tab');

      const researchTabs: ResearchTabKey[] = [
        'comparison',
        'anomaly',
        'classification',
        'hybrid',
        'explainability',
        'playground',
      ];
      const consoleTabs: ConsoleTabKey[] = ['overview', 'analyze', 'history', 'threat-intel'];

      if (areaParam === 'research' || (tabParam && researchTabs.includes(tabParam as ResearchTabKey))) {
        return {
          area: 'research',
          consoleTab: 'overview',
          researchTab: (tabParam as ResearchTabKey) || 'overview',
        };
      }

      if (tabParam && consoleTabs.includes(tabParam as ConsoleTabKey)) {
        return {
          area: 'console',
          consoleTab: tabParam as ConsoleTabKey,
          researchTab: 'overview',
        };
      }
    } catch {
      // Fallback if window/location is unavailable
    }

    return {
      area: 'console',
      consoleTab: 'overview',
      researchTab: 'overview',
    };
  };

  const [initial] = useState(getInitialState);
  const [activeArea, setActiveArea] = useState<AppArea>(initial.area);
  const [activeConsoleTab, setActiveConsoleTab] = useState<ConsoleTabKey>(initial.consoleTab);
  const [activeResearchTab, setActiveResearchTab] = useState<ResearchTabKey>(initial.researchTab);

  const updateUrl = (area: AppArea, tab: string) => {
    try {
      const url = new URL(window.location.href);
      url.searchParams.set('area', area);
      url.searchParams.set('tab', tab);
      window.history.replaceState({}, '', url.toString());
    } catch {
      // Ignore in non-browser context
    }
  };

  const handleAreaChange = (area: AppArea) => {
    setActiveArea(area);
    const tab = area === 'console' ? activeConsoleTab : activeResearchTab;
    updateUrl(area, tab);
  };

  const handleConsoleTabChange = (tab: ConsoleTabKey) => {
    setActiveConsoleTab(tab);
    updateUrl('console', tab);
  };

  const handleResearchTabChange = (tab: ResearchTabKey) => {
    setActiveResearchTab(tab);
    updateUrl('research', tab);
  };

  return (
    <div className="min-h-screen bg-[#0a0e17] text-slate-100 flex flex-col font-sans selection:bg-cyan-500 selection:text-black">
      <Header
        activeArea={activeArea}
        activeConsoleTab={activeConsoleTab}
        activeResearchTab={activeResearchTab}
        onAreaChange={handleAreaChange}
        onConsoleTabChange={handleConsoleTabChange}
        onResearchTabChange={handleResearchTabChange}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* ========================================================= */}
        {/* AREA 1: DETECTION CONSOLE (PRIMARY USER EXPERIENCE)        */}
        {/* ========================================================= */}
        {activeArea === 'console' && (
          <>
            {activeConsoleTab === 'overview' && (
              <ConsoleOverview
                onNavigateToAnalyze={() => handleConsoleTabChange('analyze')}
                onNavigateToHistory={() => handleConsoleTabChange('history')}
              />
            )}
            {activeConsoleTab === 'analyze' && <AnalyzeTraffic />}
            {activeConsoleTab === 'history' && <DetectionHistory />}
            {activeConsoleTab === 'threat-intel' && <ThreatIntelligence />}
          </>
        )}

        {/* ========================================================= */}
        {/* AREA 2: RESEARCH WORKBENCH (PRESERVED SCIENTIFIC BENCHMARK)*/}
        {/* ========================================================= */}
        {activeArea === 'research' && (
          <>
            {activeResearchTab === 'overview' && <ResearchOverview />}
            {activeResearchTab === 'comparison' && <ModelComparison />}
            {activeResearchTab === 'anomaly' && <AnomalyCalibration />}
            {activeResearchTab === 'classification' && <ClassificationDiagnostics />}
            {activeResearchTab === 'hybrid' && <HybridDecisionView />}
            {activeResearchTab === 'explainability' && <ExplainabilitySpec />}
            {activeResearchTab === 'playground' && <Playground />}
          </>
        )}
      </main>

      <footer className="border-t border-slate-800/80 bg-[#0d131f] py-6 text-xs text-slate-500 font-mono mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center space-x-2">
            <Shield className="w-4 h-4 text-cyan-400" />
            <span className="font-bold text-slate-300">NETDEFY</span>
            <span>— Network Defense Intelligence</span>
            <span className="text-slate-600">|</span>
            <span>User-Facing Threat Detection Platform</span>
          </div>

          <div className="flex items-center space-x-4">
            <span className="flex items-center space-x-1">
              <Database className="w-3.5 h-3.5 text-purple-400" />
              <span>CICIDS2017 Benchmark v1</span>
            </span>
            <span className="flex items-center space-x-1">
              <Cpu className="w-3.5 h-3.5 text-cyan-400" />
              <span>Tri-Model Hybrid Engine</span>
            </span>
            <span className="flex items-center space-x-1">
              <GitBranch className="w-3.5 h-3.5 text-emerald-400" />
              <span>Phases 1–7 Certified</span>
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}
export default App;
