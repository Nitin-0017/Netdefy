import React from 'react';
import { Shield, Cpu, Activity, BarChart3, Binary, Scale, Sparkles, Terminal } from 'lucide-react';

export type TabKey =
  | 'overview'
  | 'comparison'
  | 'anomaly'
  | 'classification'
  | 'hybrid'
  | 'explainability'
  | 'playground';

interface HeaderProps {
  activeTab: TabKey;
  onTabChange: (tab: TabKey) => void;
}

export const Header: React.FC<HeaderProps> = ({ activeTab, onTabChange }) => {
  const tabs: Array<{ key: TabKey; label: string; icon: React.ReactNode }> = [
    { key: 'overview', label: 'Benchmark & Class Verification', icon: <Scale className="w-4 h-4" /> },
    { key: 'comparison', label: 'Model Evaluation Hub', icon: <BarChart3 className="w-4 h-4" /> },
    { key: 'anomaly', label: 'Anomaly Calibration', icon: <Activity className="w-4 h-4" /> },
    { key: 'classification', label: 'Classification & Errors', icon: <Binary className="w-4 h-4" /> },
    { key: 'hybrid', label: 'Hybrid Decision Logic', icon: <Cpu className="w-4 h-4" /> },
    { key: 'explainability', label: 'Explainability & XAI', icon: <Sparkles className="w-4 h-4" /> },
    { key: 'playground', label: 'Live Inference Playground', icon: <Terminal className="w-4 h-4" /> },
  ];

  return (
    <header className="border-b border-slate-800 bg-[#0d131f]/95 sticky top-0 z-50 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between py-4 border-b border-slate-800/60">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-gradient-to-tr from-cyan-600 to-blue-500 text-white shadow-lg shadow-cyan-500/20">
              <Shield className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-extrabold text-xl tracking-tight text-white">NETDEFY</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-mono font-medium">
                  AI/ML Research Workbench
                </span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
                  Phase 6.1
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Multi-Paradigm Network Anomaly Detection, Score Calibration & Threat Attribution
              </p>
            </div>
          </div>

          <div className="hidden lg:flex items-center space-x-4 text-xs font-mono">
            <div className="bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 flex items-center space-x-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span className="text-slate-300">Models Loaded:</span>
              <span className="text-cyan-400 font-semibold">IF + AE + XGBoost (v1)</span>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 flex items-center space-x-2">
              <span className="text-slate-400">Benchmark:</span>
              <span className="text-white font-semibold">CICIDS2017 (200K v1)</span>
            </div>
          </div>
        </div>

        {/* Tab Navigation */}
        <nav className="flex space-x-1 overflow-x-auto py-2.5 no-scrollbar">
          {tabs.map((tab) => {
            const isActive = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => onTabChange(tab.key)}
                className={`flex items-center space-x-2 px-3.5 py-2 rounded-lg text-xs font-medium transition-all whitespace-nowrap ${
                  isActive
                    ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 shadow-sm shadow-cyan-500/10'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                {tab.icon}
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>
      </div>
    </header>
  );
};
