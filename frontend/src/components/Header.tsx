import React from 'react';
import {
  Shield,
  ShieldAlert,
  FlaskConical,
  Activity,
  FileSearch,
  Clock,
  BookOpen,
  Scale,
  BarChart3,
  Binary,
  Cpu,
  Sparkles,
  Terminal,
} from 'lucide-react';

export type AppArea = 'console' | 'research';

export type ConsoleTabKey = 'overview' | 'analyze' | 'history' | 'threat-intel';

export type ResearchTabKey =
  | 'overview'
  | 'comparison'
  | 'anomaly'
  | 'classification'
  | 'hybrid'
  | 'explainability'
  | 'playground';

interface HeaderProps {
  activeArea: AppArea;
  activeConsoleTab: ConsoleTabKey;
  activeResearchTab: ResearchTabKey;
  onAreaChange: (area: AppArea) => void;
  onConsoleTabChange: (tab: ConsoleTabKey) => void;
  onResearchTabChange: (tab: ResearchTabKey) => void;
}

export const Header: React.FC<HeaderProps> = ({
  activeArea,
  activeConsoleTab,
  activeResearchTab,
  onAreaChange,
  onConsoleTabChange,
  onResearchTabChange,
}) => {
  const consoleTabs: Array<{ key: ConsoleTabKey; label: string; icon: React.ReactNode }> = [
    { key: 'overview', label: 'Overview', icon: <Activity className="w-4 h-4" /> },
    { key: 'analyze', label: 'Analyze Traffic', icon: <FileSearch className="w-4 h-4" /> },
    { key: 'history', label: 'Detection History', icon: <Clock className="w-4 h-4" /> },
    { key: 'threat-intel', label: 'Threat Intelligence', icon: <BookOpen className="w-4 h-4" /> },
  ];

  const researchTabs: Array<{ key: ResearchTabKey; label: string; icon: React.ReactNode }> = [
    { key: 'overview', label: 'Benchmark & Datasets', icon: <Scale className="w-4 h-4" /> },
    { key: 'comparison', label: 'Model Evaluation Hub', icon: <BarChart3 className="w-4 h-4" /> },
    { key: 'anomaly', label: 'Anomaly Calibration', icon: <Activity className="w-4 h-4" /> },
    { key: 'classification', label: 'Classification Diagnostics', icon: <Binary className="w-4 h-4" /> },
    { key: 'hybrid', label: 'Hybrid Decision Logic', icon: <Cpu className="w-4 h-4" /> },
    { key: 'explainability', label: 'Grounded XAI Spec', icon: <Sparkles className="w-4 h-4" /> },
    { key: 'playground', label: 'Inference Playground', icon: <Terminal className="w-4 h-4" /> },
  ];

  return (
    <header className="border-b border-slate-800 bg-[#0d131f]/95 sticky top-0 z-50 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Top Branding & Mode Row */}
        <div className="flex flex-col md:flex-row md:items-center justify-between py-4 border-b border-slate-800/60 gap-4">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-gradient-to-tr from-cyan-600 to-blue-500 text-white shadow-lg shadow-cyan-500/20">
              <Shield className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-extrabold text-xl tracking-tight text-white">NETDEFY</span>
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-mono font-medium">
                  {activeArea === 'console' ? 'Threat Detection Platform' : 'Research Workbench'}
                </span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono hidden sm:inline-block">
                  Live Engine
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Detect Anomalies. Understand Network Behaviour.
              </p>
            </div>
          </div>

          {/* Area Switcher & Status */}
          <div className="flex flex-wrap items-center gap-3">
            {/* Primary Mode Selector */}
            <div className="flex items-center p-1 rounded-xl bg-slate-950 border border-slate-800">
              <button
                onClick={() => onAreaChange('console')}
                className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-lg text-xs font-mono font-bold transition-all ${
                  activeArea === 'console'
                    ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <ShieldAlert className="w-3.5 h-3.5" />
                <span>Detection Console</span>
              </button>

              <button
                onClick={() => onAreaChange('research')}
                className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-lg text-xs font-mono font-bold transition-all ${
                  activeArea === 'research'
                    ? 'bg-purple-500 text-white shadow-md shadow-purple-500/20'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <FlaskConical className="w-3.5 h-3.5" />
                <span>Research Workbench</span>
              </button>
            </div>

            {/* Model Status Pill */}
            <div className="hidden lg:flex items-center space-x-2 text-xs font-mono bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span className="text-slate-400">Models:</span>
              <span className="text-cyan-400 font-semibold">IF + AE + XGBoost (v1)</span>
            </div>
          </div>
        </div>

        {/* Sub-Navigation Row */}
        <div className="flex items-center justify-between py-2">
          <nav className="flex space-x-1 overflow-x-auto no-scrollbar">
            {activeArea === 'console'
              ? consoleTabs.map((tab) => {
                  const isActive = activeConsoleTab === tab.key;
                  return (
                    <button
                      key={tab.key}
                      onClick={() => onConsoleTabChange(tab.key)}
                      className={`flex items-center space-x-2 px-3.5 py-2 rounded-lg text-xs font-medium transition-all whitespace-nowrap ${
                        isActive
                          ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 shadow-sm shadow-cyan-500/10 font-bold'
                          : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                      }`}
                    >
                      {tab.icon}
                      <span>{tab.label}</span>
                    </button>
                  );
                })
              : researchTabs.map((tab) => {
                  const isActive = activeResearchTab === tab.key;
                  return (
                    <button
                      key={tab.key}
                      onClick={() => onResearchTabChange(tab.key)}
                      className={`flex items-center space-x-2 px-3.5 py-2 rounded-lg text-xs font-medium transition-all whitespace-nowrap ${
                        isActive
                          ? 'bg-purple-500/10 text-purple-400 border border-purple-500/30 shadow-sm shadow-purple-500/10 font-bold'
                          : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                      }`}
                    >
                      {tab.icon}
                      <span>{tab.label}</span>
                    </button>
                  );
                })}
          </nav>

          {/* Quick link to toggle between areas */}
          <button
            onClick={() => onAreaChange(activeArea === 'console' ? 'research' : 'console')}
            className="text-xs font-mono text-slate-400 hover:text-cyan-300 hidden sm:flex items-center space-x-1 shrink-0 ml-4"
          >
            {activeArea === 'console' ? (
              <>
                <FlaskConical className="w-3.5 h-3.5 text-purple-400" />
                <span>Switch to Research & Benchmarks →</span>
              </>
            ) : (
              <>
                <ShieldAlert className="w-3.5 h-3.5 text-cyan-400" />
                <span>← Back to Detection Console</span>
              </>
            )}
          </button>
        </div>
      </div>
    </header>
  );
};
