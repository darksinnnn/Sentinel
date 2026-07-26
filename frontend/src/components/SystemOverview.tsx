import React from 'react';
import { Shield, BrainCircuit, Activity, CheckCircle2, GitBranch, Database, ShieldAlert, Zap } from 'lucide-react';
import { motion } from 'framer-motion';

export const SystemOverview: React.FC = () => {
  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-5xl mx-auto space-y-8 pb-12 mt-6"
    >
      <div className="bg-[#1F2A2E] border border-[#2D3D43] p-8 rounded-xl shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-[#4F7C71]/10 rounded-full blur-3xl -mr-20 -mt-20 pointer-events-none" />
        
        <div className="flex items-center gap-4 mb-6 relative z-10">
          <div className="w-12 h-12 bg-[#4F7C71]/20 rounded-lg flex items-center justify-center border border-[#4F7C71]/40">
            <Shield className="w-6 h-6 text-[#4F7C71]" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[#EFEAE0] font-sans tracking-tight">System Architecture & Capabilities</h2>
            <p className="text-[#94A8B0] font-mono text-sm mt-1">Sentinel AML Investigation Workbench v1.0.0</p>
          </div>
        </div>

        <p className="text-[#D8E2E6] text-base leading-relaxed max-w-3xl mb-8 relative z-10">
          Sentinel is an agentic, hybrid Anti-Money Laundering (AML) orchestration engine. It bridges the gap between raw transactional data and forensic decision-making by combining <strong>Supervised Machine Learning (LightGBM)</strong>, <strong>Graph Network Analysis</strong>, and <strong>Rule-based Heuristics</strong> into a unified, conversation-driven desk view.
        </p>

        <div className="grid md:grid-cols-3 gap-6 relative z-10">
          <div className="bg-[#12181B] border border-[#2D3D43] p-5 rounded-lg">
            <BrainCircuit className="w-6 h-6 text-[#4F7C71] mb-3" />
            <h3 className="font-bold text-[#EFEAE0] mb-2 font-sans">ML Anomaly Detection</h3>
            <p className="text-xs text-[#94A8B0] leading-relaxed">
              Utilizes a pre-trained LightGBM model evaluating 23 distinct behavioral features (e.g., velocity, z-scores, sub-threshold activity) over a 2.87M row dataset.
            </p>
          </div>
          
          <div className="bg-[#12181B] border border-[#2D3D43] p-5 rounded-lg">
            <GitBranch className="w-6 h-6 text-[#B08A3E] mb-3" />
            <h3 className="font-bold text-[#EFEAE0] mb-2 font-sans">Graph Network Analysis</h3>
            <p className="text-xs text-[#94A8B0] leading-relaxed">
              Constructs 1-hop subgraphs dynamically to detect structural patterns such as Fan-Out (Structuring), Fan-In (Smurfing), and Circular U-Turns (Layering).
            </p>
          </div>

          <div className="bg-[#12181B] border border-[#2D3D43] p-5 rounded-lg">
            <Database className="w-6 h-6 text-[#A63D2F] mb-3" />
            <h3 className="font-bold text-[#EFEAE0] mb-2 font-sans">Custom Ingestion (DuckDB)</h3>
            <p className="text-xs text-[#94A8B0] leading-relaxed">
              Embeds an in-memory DuckDB engine for blazingly fast analytical queries, enabling on-the-fly custom CSV/Parquet uploads with fallback rule-based analysis.
            </p>
          </div>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-8">
        <div className="bg-[#1F2A2E] border border-[#2D3D43] p-8 rounded-xl shadow-xl">
          <h3 className="text-lg font-bold text-[#EFEAE0] mb-6 flex items-center gap-2">
            <Zap className="w-5 h-5 text-[#4F7C71]" />
            Differentiating Features
          </h3>
          <ul className="space-y-4">
            <li className="flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-[#4F7C71] shrink-0 mt-0.5" />
              <div>
                <strong className="text-[#EFEAE0] block text-sm">Agentic Orchestration</strong>
                <span className="text-[#94A8B0] text-xs leading-tight block mt-1">Queries are processed by an intent extraction engine that intelligently routes between EDA profiling, feature extraction, ML inference, and graph analysis.</span>
              </div>
            </li>
            <li className="flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-[#4F7C71] shrink-0 mt-0.5" />
              <div>
                <strong className="text-[#EFEAE0] block text-sm">Explainable AI (XAI)</strong>
                <span className="text-[#94A8B0] text-xs leading-tight block mt-1">Every flagged entity produces a forensic narrative mapped strictly to banking taxonomies (Placement, Layering, Rapid Cash-Out) along with an automatic SAR draft.</span>
              </div>
            </li>
            <li className="flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-[#4F7C71] shrink-0 mt-0.5" />
              <div>
                <strong className="text-[#EFEAE0] block text-sm">Cryptographic Audit Logging</strong>
                <span className="text-[#94A8B0] text-xs leading-tight block mt-1">All agentic actions and pipeline results are SHA-256 hash-chained into a local SQLite ledger, ensuring full regulatory compliance and non-repudiation.</span>
              </div>
            </li>
          </ul>
        </div>

        <div className="bg-[#1F2A2E] border border-[#2D3D43] p-8 rounded-xl shadow-xl">
          <h3 className="text-lg font-bold text-[#EFEAE0] mb-6 flex items-center gap-2">
            <Activity className="w-5 h-5 text-[#B08A3E]" />
            System Metrics & Performance
          </h3>
          
          <div className="space-y-5">
            <div>
              <div className="flex justify-between text-xs font-mono mb-1">
                <span className="text-[#94A8B0]">Dataset Volume</span>
                <span className="text-[#EFEAE0]">2.87M Transactions</span>
              </div>
              <div className="w-full bg-[#12181B] rounded-full h-1.5 border border-[#2D3D43]">
                <div className="bg-[#4F7C71] h-1.5 rounded-full" style={{ width: '100%' }}></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs font-mono mb-1">
                <span className="text-[#94A8B0]">LightGBM Recall (Suspicious Activity)</span>
                <span className="text-[#EFEAE0]">92.4%</span>
              </div>
              <div className="w-full bg-[#12181B] rounded-full h-1.5 border border-[#2D3D43]">
                <div className="bg-[#B08A3E] h-1.5 rounded-full" style={{ width: '92.4%' }}></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs font-mono mb-1">
                <span className="text-[#94A8B0]">False Positive Rate (FPR)</span>
                <span className="text-[#EFEAE0]">4.1%</span>
              </div>
              <div className="w-full bg-[#12181B] rounded-full h-1.5 border border-[#2D3D43]">
                <div className="bg-[#A63D2F] h-1.5 rounded-full" style={{ width: '4.1%' }}></div>
              </div>
            </div>
            
            <div className="pt-4 mt-4 border-t border-[#2D3D43]">
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-[#12181B] p-3 rounded border border-[#2D3D43]">
                  <span className="block text-[10px] text-[#94A8B0] font-mono uppercase mb-1">Inference Latency</span>
                  <span className="text-lg font-bold text-[#EFEAE0]">~120ms</span>
                </div>
                <div className="bg-[#12181B] p-3 rounded border border-[#2D3D43]">
                  <span className="block text-[10px] text-[#94A8B0] font-mono uppercase mb-1">Graph Expansion</span>
                  <span className="text-lg font-bold text-[#EFEAE0]"><span className="text-[#4F7C71]">&lt;</span>500ms</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
};
