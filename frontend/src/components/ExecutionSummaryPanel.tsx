import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { Compass, Terminal } from 'lucide-react';
import type { ExecutionSummary } from '../types/outputContract';

interface ExecutionSummaryPanelProps {
  summary: ExecutionSummary;
}

export const ExecutionSummaryPanel: React.FC<ExecutionSummaryPanelProps> = ({ summary }) => {
  const shouldReduceMotion = useReducedMotion();

  const containerVariants = {
    hidden: { opacity: 0, y: shouldReduceMotion ? 0 : 12 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.3 }
    }
  };

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="bg-[#1F2A2E] border border-[#2D3D43] rounded-lg p-5 shadow-md mb-6 font-sans text-sm text-[#EFEAE0]"
    >
      <div className="flex items-center justify-between border-b border-[#2D3D43] pb-3 mb-4">
        <div className="flex items-center gap-2">
          <Compass className="w-4 h-4 text-[#4F7C71]" />
          <h3 className="font-serif font-bold text-base text-[#EFEAE0]">Forensic Execution Ledger</h3>
        </div>
        <span className="font-mono text-xs text-[#4F7C71] border border-[#4F7C71]/40 px-2 py-0.5 rounded-xs bg-[#12181B]">
          INTENT: {summary.detected_intent.toUpperCase()}
        </span>
      </div>

      {/* Monospace Ledger Checklist (No rounded pills or badge chrome) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4 text-xs font-mono">
        <div>
          <span className="text-[#94A8B0] block mb-2 uppercase tracking-wider text-[11px] border-b border-[#2D3D43] pb-1">
            ✓ Invoked Tools ({summary.tools_invoked.length})
          </span>
          <div className="space-y-1 text-[#64978B]">
            {summary.tools_invoked.map((tool) => (
              <div key={tool} className="flex items-center gap-2">
                <span className="text-[#4F7C71]">✓</span>
                <span className="font-semibold text-[#EFEAE0]">{tool}</span>
              </div>
            ))}
          </div>
        </div>

        <div>
          <span className="text-[#94A8B0] block mb-2 uppercase tracking-wider text-[11px] border-b border-[#2D3D43] pb-1">
            ✗ Skipped Tools ({summary.tools_skipped.length})
          </span>
          <div className="space-y-1 text-[#94A8B0]/50">
            {summary.tools_skipped.map((tool) => (
              <div key={tool} className="flex items-center gap-2">
                <span className="text-[#94A8B0]/40">✗</span>
                <span className="line-through">{tool}</span>
                <span className="text-[10px] text-[#94A8B0]/40 font-normal">(bypassed)</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Reasoning Line */}
      <div className="bg-[#12181B] p-3 rounded border border-[#2D3D43] text-xs font-mono text-[#D8E2E6] flex items-start gap-2">
        <Terminal className="w-3.5 h-3.5 text-[#4F7C71] mt-0.5 shrink-0" />
        <div>
          <span className="text-[#94A8B0]">Reasoning: </span>
          <span>{summary.reasoning}</span>
        </div>
      </div>
    </motion.div>
  );
};
