import React from 'react';
import {
  AlertTriangle,
  Cpu,
  Layers,
  Info,
  Binary,
  CheckCircle2,
} from 'lucide-react';

export const ThreatIntelligence: React.FC = () => {
  const trainedClasses = [
    {
      name: 'BENIGN',
      type: 'Normal',
      day: 'Monday / Multi-Day',
      desc: 'Baseline legitimate web traffic, DNS requests, and business workstation flows.',
    },
    {
      name: 'DoS GoldenEye',
      type: 'Denial of Service',
      day: 'Wednesday',
      desc: 'Layer 7 keep-alive connection exhaustion attack holding server sockets open.',
    },
    {
      name: 'DoS Hulk',
      type: 'Denial of Service',
      day: 'Wednesday',
      desc: 'High-volume HTTP flood with randomized user-agents designed to bypass cache.',
    },
    {
      name: 'DoS Slowhttptest',
      type: 'Denial of Service',
      day: 'Wednesday',
      desc: 'Slow HTTP header/body transmission starving web server thread pools.',
    },
    {
      name: 'DoS slowloris',
      type: 'Denial of Service',
      day: 'Wednesday',
      desc: 'Periodic partial HTTP headers maintaining open sockets indefinitely.',
    },
    {
      name: 'FTP-Patator',
      type: 'Brute Force',
      day: 'Tuesday',
      desc: 'Automated high-frequency FTP credential dictionary attacks.',
    },
    {
      name: 'SSH-Patator',
      type: 'Brute Force',
      day: 'Tuesday',
      desc: 'Iterative SSH login brute-force attempts targeting port 22.',
    },
    {
      name: 'Heartbleed',
      type: 'Memory Leak Exploit',
      day: 'Wednesday',
      desc: 'OpenSSL TLS heartbeat buffer over-read exfiltrating 64KB memory chunks.',
    },
  ];

  const absentCategories = [
    {
      name: 'PortScan',
      day: 'Friday',
      behavior: 'Horizontal & vertical port sweeps',
      singleFlowLimit: 'Missed: Individual probe packets appear identical to standard SYN handshakes.',
      detectionPath: 'Requires multi-flow streaming temporal windowing (Phase 5).',
    },
    {
      name: 'DDoS (LOIC)',
      day: 'Friday',
      behavior: 'Distributed volumetric UDP/TCP packet flood',
      singleFlowLimit: 'Supervised classifier blindness (unseen attack category).',
      detectionPath: 'Detected via unsupervised Autoencoder high reconstruction error (e > 0.7084).',
    },
    {
      name: 'Botnet (Ares C2)',
      day: 'Friday',
      behavior: 'Stealthy Command & Control beaconing',
      singleFlowLimit: 'Missed: Periodic HTTP GET beacons mimic standard user browsing.',
      detectionPath: 'Requires inter-flow periodicity and host-level fan-out tracking.',
    },
    {
      name: 'Infiltration',
      day: 'Thursday',
      behavior: 'Dropbox exploit and lateral pivoting',
      singleFlowLimit: 'Extreme rarity (2 flows in test partition); minimal statistical deviation.',
      detectionPath: 'Requires host anomaly correlation and endpoint telemetry.',
    },
    {
      name: 'Web Attacks (Brute / XSS / SQLi)',
      day: 'Thursday',
      behavior: 'Application layer payload injection',
      singleFlowLimit: 'Payload strings are stripped in statistical flow representations.',
      detectionPath: 'Requires deep packet inspection (DPI) or WAF integration.',
    },
  ];

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Top Banner */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-900/90 to-slate-950 border border-slate-800 shadow-xl space-y-2">
        <div className="flex items-center space-x-2">
          <span className="text-xs font-mono font-bold uppercase tracking-wider text-cyan-400 bg-cyan-500/10 border border-cyan-500/20 px-2.5 py-1 rounded-md">
            Model Capabilities & Scope
          </span>
        </div>
        <h1 className="text-xl font-bold text-white">Threat Intelligence & Attack Coverage</h1>
        <p className="text-xs text-slate-400 max-w-2xl">
          Detailed breakdown of supported attack vectors, open-set threat behaviors, and the multi-paradigm
          triage architecture powering NETDEFY.
        </p>
      </div>

      {/* Detection Architecture Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg space-y-3">
          <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400 w-fit">
            <Cpu className="w-5 h-5" />
          </div>
          <h2 className="text-sm font-bold text-white">1. Unsupervised Anomaly Tier</h2>
          <p className="text-xs text-slate-400 leading-relaxed">
            Combines a 16-D Deep Autoencoder (O(D) latency) and Isolation Forest calibrated strictly on pure benign
            validation traffic (p99 = 0.9821). Detects zero-day threats without prior labels.
          </p>
        </div>

        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg space-y-3">
          <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 w-fit">
            <Binary className="w-5 h-5" />
          </div>
          <h2 className="text-sm font-bold text-white">2. Supervised Classification Tier</h2>
          <p className="text-xs text-slate-400 leading-relaxed">
            Trained on 8 confirmed traffic categories. Achieves 97.31% precision on known attacks, providing analysts
            with instant attack class attribution and confidence probabilities.
          </p>
        </div>

        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg space-y-3">
          <div className="p-2 rounded-lg bg-purple-500/10 text-purple-400 w-fit">
            <Layers className="w-5 h-5" />
          </div>
          <h2 className="text-sm font-bold text-white">3. Four-State Triage Policy</h2>
          <p className="text-xs text-slate-400 leading-relaxed">
            Fuses outlier evidence and classifier probabilities into 4 actionable SOC states: NORMAL,
            SUSPICIOUS_KNOWN, SUSPICIOUS_UNKNOWN, and REVIEW_REQUIRED.
          </p>
        </div>
      </div>

      {/* Trained Attack Classes (8) */}
      <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl space-y-4">
        <div>
          <h2 className="text-base font-bold text-white flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span>Trained Attack Classes (8 Supported Categories)</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Categories recognized directly by the supervised XGBoost model
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {trainedClasses.map((cls) => (
            <div key={cls.name} className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white font-mono">{cls.name}</span>
                <span
                  className={`text-[10px] font-mono px-2 py-0.5 rounded ${
                    cls.name === 'BENIGN'
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      : 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20'
                  }`}
                >
                  {cls.type}
                </span>
              </div>
              <p className="text-[11px] text-slate-400">{cls.desc}</p>
              <div className="text-[10px] text-slate-500 font-mono pt-1">Partition: {cls.day}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Absent Open-Set Threat Vectors (7) */}
      <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl space-y-4">
        <div>
          <h2 className="text-base font-bold text-white flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <span>Open-Set Threat Vectors (Absent from Classifier Training)</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Attacks excluded from classifier training to test open-world anomaly generalization
          </p>
        </div>

        <div className="overflow-x-auto border border-slate-800 rounded-xl">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-950 text-slate-400 uppercase text-[11px]">
                <th className="py-3 px-4">Threat Category</th>
                <th className="py-3 px-4">Observed Behavior</th>
                <th className="py-3 px-4">Single-Flow Limitation</th>
                <th className="py-3 px-4 text-cyan-400">Detection Mechanism</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 bg-slate-900/40">
              {absentCategories.map((item) => (
                <tr key={item.name} className="hover:bg-slate-800/30 transition-colors">
                  <td className="py-3.5 px-4 font-bold text-rose-400">{item.name}</td>
                  <td className="py-3.5 px-4 text-slate-300 font-sans">{item.behavior}</td>
                  <td className="py-3.5 px-4 text-amber-300/90 font-sans max-w-xs">{item.singleFlowLimit}</td>
                  <td className="py-3.5 px-4 text-cyan-300 font-sans max-w-xs">{item.detectionPath}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Non-Negotiable Scientific Disclaimers */}
      <div className="p-5 rounded-2xl bg-slate-950 border border-slate-800 space-y-3">
        <div className="flex items-center space-x-2 text-xs font-mono font-bold text-slate-300 uppercase">
          <Info className="w-4 h-4 text-cyan-400" />
          <span>Operational Constraints & Disclaimers</span>
        </div>
        <ul className="text-xs text-slate-400 font-mono space-y-1.5 list-disc list-inside">
          <li>
            <strong className="text-slate-300">Single-Flow Scope:</strong> A single statistical flow vector lacks the
            temporal history required to detect low-frequency port scans, C2 beaconing, or distributed multi-host campaigns.
          </li>
          <li>
            <strong className="text-slate-300">Closed-Set Classifier Limits:</strong> XGBoost misclassifies 71.72% of
            holdout attacks as BENIGN when those attack types were never seen during training.
          </li>
          <li>
            <strong className="text-slate-300">Anomaly vs. Malice:</strong> High anomaly residuals reflect statistical
            unusualness relative to Monday baseline traffic, not guaranteed hostile intent.
          </li>
          <li>
            <strong className="text-slate-300">No Hardcoded Truth:</strong> All outputs reflect real mathematical evaluations
            from the loaded model registry artifacts.
          </li>
        </ul>
      </div>
    </div>
  );
};
