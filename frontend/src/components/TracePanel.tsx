import React, { useState } from 'react';
import { Activity, ShieldCheck, Database, Key, ExternalLink, X } from 'lucide-react';
import type { ExecutionSummary, AuditRecord } from '../types/outputContract';
import { fetchAuditRecord } from '../api/sentinel';

interface TracePanelProps {
  summary: ExecutionSummary | null;
  auditRef: string | null;
}

export const TracePanel: React.FC<TracePanelProps> = ({ summary, auditRef }) => {
  const [auditData, setAuditData] = useState<AuditRecord | null>(null);
  const [isFetchingAudit, setIsFetchingAudit] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);

  const handleAuditClick = async () => {
    if (!auditRef) return;
    setIsFetchingAudit(true);
    setAuditError(null);
    try {
      const data = await fetchAuditRecord(auditRef);
      setAuditData(data);
    } catch (err: any) {
      setAuditError(err.message || 'Failed to fetch audit log record.');
    } finally {
      setIsFetchingAudit(false);
    }
  };

  return (
    <aside className="w-full lg:w-80 bg-[#12181B] border-t lg:border-t-0 lg:border-l border-[#2D3D43] p-4 flex flex-col h-full overflow-y-auto text-xs text-[#EFEAE0] font-sans">
      <div className="flex items-center gap-2 border-b border-[#2D3D43] pb-3 mb-4">
        <Activity className="w-4 h-4 text-[#4F7C71]" />
        <h3 className="font-serif font-bold text-base text-[#EFEAE0]">Evidence Chain & Audit Trace</h3>
      </div>

      {!summary ? (
        <div className="text-center py-10 text-[#94A8B0]/60 font-mono text-xs">
          <Database className="w-8 h-8 mx-auto mb-2 opacity-30" />
          Awaiting query execution...
        </div>
      ) : (
        <div className="space-y-6">
          {/* Vertical Evidence Chain (No boxed stepper pills) */}
          <div>
            <span className="font-mono text-[#94A8B0] uppercase text-[10px] tracking-wider block mb-3">
              Chain of Custody Execution Chain
            </span>
            <div className="relative pl-4 border-l-2 border-[#4F7C71]/40 space-y-3 font-mono">
              {summary.tools_invoked.map((tool, idx) => (
                <div key={tool} className="relative flex items-center justify-between text-xs">
                  {/* Node Dot */}
                  <div className="absolute -left-[21px] top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full bg-[#4F7C71] border-2 border-[#12181B]" />
                  
                  <div className="flex items-center gap-2">
                    <span className="text-[#94A8B0] text-[10px]">#{idx + 1}</span>
                    <span className="font-semibold text-[#EFEAE0]">{tool}</span>
                  </div>
                  <span className="text-[10px] text-[#4F7C71]">EXECUTED</span>
                </div>
              ))}
            </div>
          </div>

          {/* Audit Trail Ledger Box */}
          {auditRef && (
            <div className="bg-[#1F2A2E] p-3.5 rounded border border-[#2D3D43] shadow-sm font-mono">
              <span className="text-[#94A8B0] uppercase text-[10px] tracking-wider block mb-1">
                SHA-256 Audit Reference
              </span>
              <div className="text-sm text-[#4F7C71] font-bold mb-2 flex items-center gap-1.5">
                <Key className="w-3.5 h-3.5" />
                <span>{auditRef}</span>
              </div>
              <button
                onClick={handleAuditClick}
                disabled={isFetchingAudit}
                className="w-full bg-[#12181B] hover:bg-[#222C31] text-[#64978B] border border-[#4F7C71]/50 px-3 py-1.5 rounded font-mono text-xs flex items-center justify-center gap-1.5 transition-colors focus-visible:ring-2 focus-visible:ring-[#4F7C71] focus-visible:outline-none"
              >
                <ExternalLink className="w-3 h-3" />
                <span>{isFetchingAudit ? 'Verifying...' : 'Verify Cryptographic Hash'}</span>
              </button>
            </div>
          )}

          {/* Verification Modal / Expander */}
          {auditError && (
            <div className="p-2.5 bg-[#A63D2F]/20 text-[#A63D2F] rounded font-mono text-xs border border-[#A63D2F]/40">
              {auditError}
            </div>
          )}

          {auditData && (
            <div className="bg-[#12181B] p-3 rounded border border-[#4F7C71] font-mono text-[11px] relative shadow-lg">
              <div className="flex items-center justify-between border-b border-[#2D3D43] pb-1.5 mb-2">
                <span className="text-[#4F7C71] font-bold flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5" /> VERIFIED HASH
                </span>
                <button
                  onClick={() => setAuditData(null)}
                  className="text-[#94A8B0] hover:text-white"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
              <div className="space-y-1.5 text-[#D8E2E6] overflow-x-auto">
                <div><span className="text-[#94A8B0]">Event:</span> {auditData.event_type}</div>
                <div><span className="text-[#94A8B0]">Timestamp:</span> {auditData.timestamp}</div>
                <div className="truncate"><span className="text-[#94A8B0]">Prev Hash:</span> {auditData.prev_hash}</div>
                <div className="truncate text-[#4F7C71]"><span className="text-[#94A8B0]">Curr Hash:</span> {auditData.curr_hash}</div>
              </div>
            </div>
          )}
        </div>
      )}
    </aside>
  );
};
