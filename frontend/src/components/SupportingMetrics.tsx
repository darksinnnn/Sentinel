import React from 'react';
import { Layers, Network, ShieldAlert, TrendingUp, BarChart3, AlertTriangle } from 'lucide-react';

interface SupportingMetricsProps {
  metrics: Record<string, any>;
}

export const SupportingMetrics: React.FC<SupportingMetricsProps> = ({ metrics }) => {
  if (!metrics || Object.keys(metrics).length === 0) return null;

  const {
    risk_distribution,
    graph,
    overview,
    amount_statistics,
    pattern_prevalence,
    ofac_sanctions_matches,
    trajectory_score,
    trajectory_alert
  } = metrics;

  return (
    <div className="space-y-5 mb-6 text-[#EFEAE0] font-sans">

      {/* ── 1. Graph / Network Structural Analysis Box ──────────────────────── */}
      {graph && (
        <div className="bg-[#1F2A2E] border border-[#3C6158] rounded-lg p-5 shadow-lg relative overflow-hidden">
          <div className="flex items-center justify-between border-b border-[#2D3D43] pb-2.5 mb-4">
            <div className="flex items-center gap-2">
              <Network className="w-5 h-5 text-[#4F7C71]" />
              <h4 className="font-serif font-bold text-sm tracking-tight text-[#EFEAE0]">
                Graph Network Structural Analysis (NetworkX Engine)
              </h4>
            </div>
            <span className="font-mono text-xs bg-[#12181B] text-[#4F7C71] px-2.5 py-1 rounded border border-[#2D3D43]">
              1-Hop Seed Topology Scan
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 bg-[#12181B] p-3 rounded border border-[#2D3D43] font-mono text-xs mb-3">
            <div>
              <span className="text-[#94A8B0] text-[10px] block uppercase">Network Nodes</span>
              <span className="font-bold text-[#EFEAE0]">{graph.total_nodes?.toLocaleString() ?? 0}</span>
            </div>
            <div>
              <span className="text-[#94A8B0] text-[10px] block uppercase">Network Edges</span>
              <span className="font-bold text-[#EFEAE0]">{graph.total_edges?.toLocaleString() ?? 0}</span>
            </div>
            <div>
              <span className="text-[#94A8B0] text-[10px] block uppercase">Smurfing (Fan-Out)</span>
              <span className="font-bold text-[#FFEDD5]">{graph.fan_out_count ?? 0}</span>
            </div>
            <div>
              <span className="text-[#94A8B0] text-[10px] block uppercase">Aggregation (Fan-In)</span>
              <span className="font-bold text-[#FFEDD5]">{graph.fan_in_count ?? 0}</span>
            </div>
            <div>
              <span className="text-[#94A8B0] text-[10px] block uppercase">Layering (Cycles)</span>
              <span className="font-bold text-[#A63D2F]">{graph.cycle_node_count ?? 0}</span>
            </div>
          </div>

          {graph.cycle_node_count > 0 && (
            <div className="flex items-center gap-2 bg-[#A63D2F]/20 text-[#A63D2F] p-2.5 rounded border border-[#A63D2F]/40 text-xs font-mono">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>
                CRITICAL TOPOLOGY WARNING: {graph.cycle_node_count} circular fund-routing cycles detected (money laundering layering pattern).
              </span>
            </div>
          )}
        </div>
      )}

      {/* ── 2. Trajectory Ledger Score Box ──────────────────────────────────── */}
      {trajectory_score !== undefined && (
        <div className="bg-[#1F2A2E] border border-[#2D3D43] rounded-lg p-4 shadow-md font-mono text-xs">
          <div className="flex items-center justify-between border-b border-[#2D3D43] pb-2 mb-3">
            <div className="flex items-center gap-2 text-[#4F7C71]">
              <TrendingUp className="w-4 h-4" />
              <h4 className="font-serif font-bold text-sm text-[#EFEAE0]">Accumulating Trajectory Ledger (Decay-Weighted)</h4>
            </div>
            {trajectory_alert ? (
              <span className="bg-[#A63D2F] text-white text-[10px] px-2 py-0.5 rounded font-bold uppercase tracking-wider">
                TRAJECTORY ALERT ACTIVE
              </span>
            ) : (
              <span className="bg-[#4F7C71]/20 text-[#4F7C71] text-[10px] px-2 py-0.5 rounded uppercase">
                ACCUMULATION MONITORING
              </span>
            )}
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 bg-[#12181B] p-3 rounded border border-[#2D3D43]">
            <div>
              <span className="text-[#94A8B0] text-[10px] block uppercase">Decayed Ledger Score</span>
              <span className={`font-bold text-sm ${trajectory_alert ? 'text-[#A63D2F]' : 'text-[#EFEAE0]'}`}>
                {trajectory_score.toFixed(4)}
              </span>
            </div>
            <div>
              <span className="text-[#94A8B0] text-[10px] block uppercase">Alert Threshold</span>
              <span className="font-bold text-[#EFEAE0]">0.9000</span>
            </div>
            <div>
              <span className="text-[#94A8B0] text-[10px] block uppercase">Accumulation Status</span>
              <span className="font-bold text-[#EFEAE0]">{trajectory_alert ? 'ESCALATED TO HIGH' : 'NORMAL'}</span>
            </div>
          </div>
        </div>
      )}

      {/* ── 3. Sanctions Hit Alert Box ───────────────────────────────────────── */}
      {ofac_sanctions_matches && ofac_sanctions_matches.length > 0 && (
        <div className="bg-[#A63D2F]/15 border border-[#A63D2F]/60 rounded-lg p-4 shadow-lg text-[#EFEAE0]">
          <div className="flex items-center gap-2 border-b border-[#A63D2F]/40 pb-2 mb-3 text-[#A63D2F]">
            <ShieldAlert className="w-5 h-5 shrink-0" />
            <h4 className="font-serif font-bold text-sm uppercase tracking-wider">
              US Treasury OFAC Sanctions List Match ({ofac_sanctions_matches.length} Candidate(s))
            </h4>
          </div>
          <div className="space-y-2">
            {ofac_sanctions_matches.map((m: any, idx: number) => (
              <div key={idx} className="bg-[#12181B] p-3 rounded border border-[#A63D2F]/40 font-mono text-xs flex justify-between items-center">
                <div>
                  <span className="font-bold text-[#EFEAE0] text-sm block">{m.name}</span>
                  <span className="text-[#94A8B0] text-[10px]">
                    UID: {m.uid} | Type: {m.type} {m.aliases ? `| Aliases: ${m.aliases}` : ''}
                  </span>
                </div>
                <div className="text-right">
                  <span className="bg-[#A63D2F] text-white text-[10px] px-2 py-0.5 rounded font-bold uppercase block mb-1">
                    {m.match_type || 'MATCH'}
                  </span>
                  <span className="text-[#94A8B0] text-[10px]">
                    Score: {((m.similarity_score || 1.0) * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── 4. Population Breakdown Ledger Bar ───────────────────────────────── */}
      {risk_distribution && (
        <div className="bg-[#1F2A2E] border border-[#2D3D43] rounded-lg p-5 shadow-md">
          <div className="flex items-center justify-between border-b border-[#2D3D43] pb-2.5 mb-4">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-[#4F7C71]" />
              <h4 className="font-serif font-bold text-sm tracking-tight text-[#EFEAE0]">
                Dataset Population Breakdown
              </h4>
            </div>
            <span className="font-mono text-xs text-[#94A8B0]">
              Total Scored: <strong className="text-[#EFEAE0]">
                {(Object.values(risk_distribution) as number[]).reduce((a, b) => a + b, 0).toLocaleString()}
              </strong>
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-[#12181B] p-3 rounded border border-[#2D3D43] font-mono text-xs">
            {Object.entries(risk_distribution).map(([key, val]) => (
              <div key={key} className="flex items-center gap-2">
                <span className={`w-2.5 h-2.5 rounded-xs shrink-0 ${
                  key === 'high' ? 'bg-[#A63D2F]' : key === 'medium' ? 'bg-[#B08A3E]' : 'bg-[#6B7280]'
                }`} />
                <div>
                  <span className="text-[#94A8B0] text-[10px] block uppercase">{key.replace('_', ' ')}</span>
                  <span className="font-bold text-[#EFEAE0]">{(val as number).toLocaleString()}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── 5. Rich EDA Profiling Statistics Box ──────────────────────────────── */}
      {(overview || amount_statistics || pattern_prevalence) && (
        <div className="bg-[#1F2A2E] border border-[#2D3D43] rounded-lg p-5 shadow-md font-mono text-xs">
          <div className="flex items-center gap-2 border-b border-[#2D3D43] pb-2.5 mb-4 text-[#4F7C71]">
            <BarChart3 className="w-4 h-4" />
            <h4 className="font-serif font-bold text-sm text-[#EFEAE0]">Comprehensive Dataset EDA Summary</h4>
          </div>

          {overview && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-[#12181B] p-3 rounded border border-[#2D3D43] mb-3">
              <div>
                <span className="text-[#94A8B0] text-[10px] block uppercase">Total Transactions</span>
                <span className="font-bold text-[#EFEAE0]">{overview.total_transactions?.toLocaleString()}</span>
              </div>
              <div>
                <span className="text-[#94A8B0] text-[10px] block uppercase">Unique Senders</span>
                <span className="font-bold text-[#EFEAE0]">{overview.unique_senders?.toLocaleString()}</span>
              </div>
              <div>
                <span className="text-[#94A8B0] text-[10px] block uppercase">Temporal Range Start</span>
                <span className="font-bold text-[#4F7C71]">{overview.min_txn_time?.split(' ')[0]}</span>
              </div>
              <div>
                <span className="text-[#94A8B0] text-[10px] block uppercase">Temporal Range End</span>
                <span className="font-bold text-[#4F7C71]">{overview.max_txn_time?.split(' ')[0]}</span>
              </div>
            </div>
          )}

          {amount_statistics && (
            <div className="bg-[#12181B] p-3 rounded border border-[#2D3D43] mb-3">
              <span className="text-[#94A8B0] text-[10px] block uppercase mb-2">Monetary Distribution Percentiles</span>
              <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 text-center">
                <div className="bg-[#1F2A2E] p-2 rounded">
                  <span className="text-[#94A8B0] text-[9px] block">MEAN</span>
                  <span className="font-bold text-[#EFEAE0]">${amount_statistics.mean_amount?.toLocaleString()}</span>
                </div>
                <div className="bg-[#1F2A2E] p-2 rounded">
                  <span className="text-[#94A8B0] text-[9px] block">MEDIAN</span>
                  <span className="font-bold text-[#EFEAE0]">${amount_statistics.median_amount?.toLocaleString()}</span>
                </div>
                <div className="bg-[#1F2A2E] p-2 rounded">
                  <span className="text-[#94A8B0] text-[9px] block">P25</span>
                  <span className="font-bold text-[#EFEAE0]">${amount_statistics.p25_amount?.toLocaleString()}</span>
                </div>
                <div className="bg-[#1F2A2E] p-2 rounded">
                  <span className="text-[#94A8B0] text-[9px] block">P75</span>
                  <span className="font-bold text-[#EFEAE0]">${amount_statistics.p75_amount?.toLocaleString()}</span>
                </div>
                <div className="bg-[#1F2A2E] p-2 rounded">
                  <span className="text-[#94A8B0] text-[9px] block">P95</span>
                  <span className="font-bold text-[#EFEAE0]">${amount_statistics.p95_amount?.toLocaleString()}</span>
                </div>
                <div className="bg-[#1F2A2E] p-2 rounded">
                  <span className="text-[#94A8B0] text-[9px] block">P99</span>
                  <span className="font-bold text-[#A63D2F]">${amount_statistics.p99_amount?.toLocaleString()}</span>
                </div>
              </div>
            </div>
          )}

          {pattern_prevalence && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 bg-[#12181B] p-3 rounded border border-[#2D3D43]">
              <div>
                <span className="text-[#94A8B0] text-[10px] block uppercase">Structuring Prevalence</span>
                <span className="font-bold text-[#FFEDD5]">
                  {pattern_prevalence.structuring_count?.toLocaleString()} ({pattern_prevalence.structuring_rate_pct}%)
                </span>
              </div>
              <div>
                <span className="text-[#94A8B0] text-[10px] block uppercase">Rapid Cashout Prevalence</span>
                <span className="font-bold text-[#FFEDD5]">
                  {pattern_prevalence.rapid_cashout_count?.toLocaleString()} ({pattern_prevalence.rapid_cashout_rate_pct}%)
                </span>
              </div>
              <div>
                <span className="text-[#94A8B0] text-[10px] block uppercase">Round Number Anomaly</span>
                <span className="font-bold text-[#FFEDD5]">
                  {pattern_prevalence.round_number_count?.toLocaleString()} ({pattern_prevalence.round_number_rate_pct}%)
                </span>
              </div>
            </div>
          )}
        </div>
      )}

    </div>
  );
};
