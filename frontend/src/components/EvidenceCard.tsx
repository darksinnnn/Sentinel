import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { FileText, ChevronDown, ChevronUp, Layers, Activity, AlertTriangle, DollarSign } from 'lucide-react';
import type { FlaggedItem } from '../types/outputContract';
import { VerdictStamp } from './VerdictStamp';

interface EvidenceCardProps {
  item: FlaggedItem;
  index: number;
}

/** Formats an evidence value into a human-readable string. */
function fmtValue(key: string, val: any): string {
  if (val === null || val === undefined) return 'N/A';
  if (typeof val === 'boolean') return val ? '✓  YES' : '✗  NO';
  if (typeof val === 'number') {
    if (key.includes('amount') || key.includes('balance') || key.includes('out_amount') || key.includes('in_amount'))
      return `$${val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    if (key.includes('rate') || key.includes('pct')) return `${(val * 100).toFixed(2)}%`;
    if (key.includes('zscore') || key.includes('ratio') || key.includes('score')) return val.toFixed(4);
    return val.toLocaleString();
  }
  if (typeof val === 'object') return JSON.stringify(val, null, 1);
  return String(val);
}

/** Colour-codes a value cell based on whether the metric is anomalous. */
function getCellClass(key: string, val: any): string {
  if (typeof val === 'boolean') return val ? 'text-[#A63D2F] font-bold' : 'text-[#3C6158]';
  if (typeof val === 'number') {
    if (key.includes('zscore') && val > 2.0) return 'text-[#A63D2F] font-bold';
    if (key.includes('zscore') && val > 1.0) return 'text-[#B08A3E] font-bold';
    if (key.includes('score') && val > 0.7) return 'text-[#A63D2F] font-bold';
    if (key.includes('trajectory_alert') && val) return 'text-[#A63D2F] font-bold';
  }
  return 'text-[#1F2A2E]';
}

/** Returns a small label icon for a known metric category. */
function metricIcon(key: string) {
  if (key.includes('amount') || key.includes('balance')) return <DollarSign className="w-3 h-3 text-[#6B7280] shrink-0" />;
  if (key.includes('zscore') || key.includes('velocity')) return <Activity className="w-3 h-3 text-[#B08A3E] shrink-0" />;
  if (key.includes('alert') || key.includes('risk')) return <AlertTriangle className="w-3 h-3 text-[#A63D2F] shrink-0" />;
  if (key.includes('degree') || key.includes('cycle') || key.includes('graph')) return <Layers className="w-3 h-3 text-[#3C6158] shrink-0" />;
  return null;
}

export const EvidenceCard: React.FC<EvidenceCardProps> = ({ item, index }) => {
  const [showSar, setShowSar] = React.useState(false);
  const shouldReduceMotion = useReducedMotion();

  const cardVariants = {
    hidden: { opacity: 0, y: shouldReduceMotion ? 0 : 20 },
    visible: {
      opacity: 1, y: 0,
      transition: { duration: shouldReduceMotion ? 0 : 0.4, delay: shouldReduceMotion ? 0 : index * 0.08 },
    },
  };

  // Evidence entries, skip empty objects
  const evidenceEntries = Object.entries(item.evidence || {}).filter(
    ([, v]) => !(typeof v === 'object' && v !== null && Object.keys(v).length === 0)
  );

  return (
    <motion.div
      variants={cardVariants}
      initial="hidden"
      animate="visible"
      className="bg-[#EFEAE0] text-[#1F2A2E] rounded-lg p-5 mb-5 shadow-xl border border-[#D6CDBA] relative overflow-hidden font-sans"
    >
      {/* ── Header row ────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 border-b border-[#D6CDBA] pb-3 mb-4">
        <div>
          <span className="font-mono text-xs text-[#6B7280] uppercase tracking-wider">
            EVIDENCE RECORD #{index + 1} ({item.entity_type.toUpperCase()})
          </span>
          <h4 className="font-mono text-lg font-bold text-[#1F2A2E] tracking-tight mt-0.5">
            ID: <span className="text-[#3C6158]">{item.entity_id}</span>
          </h4>
        </div>
        <VerdictStamp riskLevel={item.risk_level} />
      </div>

      {/* ── Core classification grid ───────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-[#E5DFD3] p-3 rounded border border-[#D6CDBA] mb-4 font-mono text-xs">
        <div>
          <span className="text-[#6B7280] block text-[10px] uppercase">Detected Pattern</span>
          <span className="font-semibold text-[#1F2A2E] break-all leading-tight block">{item.detected_pattern}</span>
        </div>
        <div>
          <span className="text-[#6B7280] block text-[10px] uppercase">Risk Score</span>
          <span className="font-bold text-[#A63D2F]">{item.risk_score.toFixed(4)}</span>
        </div>
        <div>
          <span className="text-[#6B7280] block text-[10px] uppercase">Recommended Action</span>
          <span className="font-semibold text-[#3C6158] uppercase">{item.recommended_action || 'REVIEW'}</span>
        </div>
        <div>
          <span className="text-[#6B7280] block text-[10px] uppercase">Classification</span>
          <span className="font-semibold text-[#1F2A2E] capitalize">{item.risk_level.replace('_', ' ')}</span>
        </div>
      </div>

      {/* ── Analyst narrative ──────────────────────────────────────── */}
      <div className="mb-4">
        <span className="font-serif font-semibold text-xs text-[#6B7280] uppercase tracking-wider block mb-1">
          Forensic Analyst Narrative
        </span>
        <p className="text-sm text-[#261F16] leading-relaxed bg-[#F7F4EC] p-3 rounded border-l-4 border-[#4F7C71]">
          {item.explanation}
        </p>
      </div>

      {/* ── ALL EVIDENCE STATS — always visible ───────────────────── */}
      {evidenceEntries.length > 0 && (
        <div className="mb-4">
          <span className="font-serif font-semibold text-xs text-[#6B7280] uppercase tracking-wider block mb-2">
            Statistical Evidence & Feature Proof
          </span>

          {/* Metric tiles grid */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
            {evidenceEntries.map(([key, val]) => {
              const isFlag = typeof val === 'boolean' && val === true;
              const isZHigh = key.includes('zscore') && typeof val === 'number' && val > 2.0;
              const highlight = isFlag || isZHigh;

              return (
                <div
                  key={key}
                  className={`p-2.5 rounded border font-mono text-xs flex flex-col gap-1 ${
                    highlight
                      ? 'bg-[#A63D2F]/10 border-[#A63D2F]/40'
                      : 'bg-[#E5DFD3] border-[#D6CDBA]'
                  }`}
                >
                  <div className="flex items-center gap-1">
                    {metricIcon(key)}
                    <span className="text-[#6B7280] text-[9px] uppercase leading-tight break-all">
                      {key.replace(/_/g, ' ')}
                    </span>
                    {highlight && <AlertTriangle className="w-2.5 h-2.5 text-[#A63D2F] ml-auto shrink-0" />}
                  </div>
                  <span className={`font-bold text-sm leading-snug break-all ${getCellClass(key, val)}`}>
                    {fmtValue(key, val)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── SAR Draft (toggle) ─────────────────────────────────────── */}
      {item.sar_draft && (
        <div className="mt-3">
          <button
            onClick={() => setShowSar(!showSar)}
            className="flex items-center gap-1.5 text-xs font-mono text-[#A63D2F] hover:text-[#1F2A2E] transition-colors focus-visible:ring-2 focus-visible:ring-[#A63D2F] focus-visible:outline-none rounded px-1"
          >
            <FileText className="w-3.5 h-3.5" />
            <span>{showSar ? 'Hide SAR Draft' : 'View Regulatory Filing Draft (SAR)'}</span>
            {showSar ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>

          {showSar && (
            <div className="mt-2 bg-[#1F2A2E] text-[#EFEAE0] p-4 rounded-lg border border-[#A63D2F]/40 shadow-inner">
              <div className="flex items-center justify-between border-b border-[#2D3D43] pb-2 mb-2">
                <div className="flex items-center gap-2 text-[#A63D2F]">
                  <FileText className="w-4 h-4" />
                  <span className="font-mono text-xs font-bold uppercase tracking-wider">
                    Regulatory Filing Draft (Form SAR)
                  </span>
                </div>
                <span className="text-[10px] font-mono bg-[#A63D2F]/20 text-[#A63D2F] px-2 py-0.5 rounded uppercase">
                  CONFIDENTIAL / COMPLIANCE USE ONLY
                </span>
              </div>
              <p className="font-sans text-xs text-[#D8E2E6] leading-relaxed whitespace-pre-line">
                {item.sar_draft}
              </p>
            </div>
          )}
        </div>
      )}
    </motion.div>
  );
};
