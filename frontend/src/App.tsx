import { useState } from 'react';
import { Header, TabKey } from './components/Header';
import { ResearchOverview } from './components/ResearchOverview';
import { ModelComparison } from './components/ModelComparison';
import { AnomalyCalibration } from './components/AnomalyCalibration';
import { ClassificationDiagnostics } from './components/ClassificationDiagnostics';
import { HybridDecisionView } from './components/HybridDecisionView';
import { ExplainabilitySpec } from './components/ExplainabilitySpec';
import { Playground } from './components/Playground';
import { Shield, GitBranch, Database, Cpu } from 'lucide-react';

export function App() {
  const [activeTab, setActiveTab] = useState<TabKey>('overview');

  return (
    <div className="min-h-screen bg-[#0b0f17] text-slate-100 flex flex-col font-sans">
      <Header activeTab={activeTab} onTabChange={setActiveTab} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'overview' && <ResearchOverview />}
        {activeTab === 'comparison' && <ModelComparison />}
        {activeTab === 'anomaly' && <AnomalyCalibration />}
        {activeTab === 'classification' && <ClassificationDiagnostics />}
        {activeTab === 'hybrid' && <HybridDecisionView />}
        {activeTab === 'explainability' && <ExplainabilitySpec />}
        {activeTab === 'playground' && <Playground />}
      </main>

      <footer className="border-t border-slate-800/80 bg-[#0d131f] py-6 text-xs text-slate-500 font-mono">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center space-x-2">
            <Shield className="w-4 h-4 text-cyan-400" />
            <span className="font-bold text-slate-300">NETDEFY</span>
            <span>— Network Defense Intelligence</span>
            <span className="text-slate-600">|</span>
            <span>AI/ML Research & Engineering Portfolio</span>
          </div>

          <div className="flex items-center space-x-4">
            <span className="flex items-center space-x-1">
              <Database className="w-3.5 h-3.5 text-purple-400" />
              <span>Benchmark v1 (200K)</span>
            </span>
            <span className="flex items-center space-x-1">
              <Cpu className="w-3.5 h-3.5 text-cyan-400" />
              <span>Tri-Model Hybrid Engine</span>
            </span>
            <span className="flex items-center space-x-1">
              <GitBranch className="w-3.5 h-3.5 text-emerald-400" />
              <span>Phases 1–6.1 Certified</span>
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
