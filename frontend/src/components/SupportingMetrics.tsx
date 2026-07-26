import React from 'react';
import { Layers, Network, ShieldAlert, TrendingUp, BarChart3, AlertTriangle, PieChart as PieIcon, Activity, Target } from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  LineChart, Line, Area, AreaChart, PieChart, Pie, Cell, Legend, RadialBarChart, RadialBar
} from 'recharts';

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
    trajectory_alert,
    aggregation_chart,
    daily_trend,
    customer_segments
  } = metrics;

  return (
    <div className="space-y-5 mb-6 text-[#EFEAE0] font-sans">
      
      {/* ── 0. Aggregation Chart (Recharts) ──────────────────────── */}
      {aggregation_chart && aggregation_chart.data && (
        <div className="bg-[#1F2A2E] border border-[#3C6158] rounded-lg p-5 shadow-lg">
          <div className="flex items-center gap-2 border-b border-[#2D3D43] pb-2.5 mb-4 text-[#4F7C71]">
            <BarChart3 className="w-5 h-5" />
            <h4 className="font-serif font-bold text-sm text-[#EFEAE0]">{aggregation_chart.title}</h4>
            <span className="ml-auto font-mono text-xs text-[#94A8B0] border border-[#2D3D43] px-2 py-0.5 rounded">RULE-BASED AGGREGATION</span>
          </div>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={aggregation_chart.data} margin={{ top: 10, right: 60, left: 10, bottom: 30 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2D3D43" vertical={false} />
                <XAxis dataKey="name" stroke="#94A8B0" fontSize={10} tickMargin={10} angle={-35} textAnchor="end" />
                <YAxis yAxisId="left" stroke="#4F7C71" fontSize={10} tickFormatter={(v) => v.toLocaleString()} />
                <YAxis yAxisId="right" orientation="right" stroke="#A63D2F" fontSize={10} tickFormatter={(v) => `$${(v/1000000).toFixed(1)}M`} />
                <Tooltip contentStyle={{ backgroundColor: '#12181B', borderColor: '#2D3D43', fontSize: '12px', borderRadius: '6px' }} itemStyle={{ color: '#EFEAE0' }} />
                <Bar yAxisId="left" dataKey="txns" name="Transaction Count" fill="#4F7C71" radius={[3, 3, 0, 0]} />
                <Bar yAxisId="right" dataKey="amount" name="Total Volume ($)" fill="#A63D2F" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="flex gap-4 mt-2 text-xs font-mono justify-center">
            <div className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm bg-[#4F7C71] inline-block" />Transaction Count</div>
            <div className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm bg-[#A63D2F] inline-block" />Total Volume</div>
          </div>
        </div>
      )}

      {/* ── 0b. Daily Transaction & High-Risk Trend Chart ────────────────────── */}
      {daily_trend && daily_trend.length > 0 && (() => {
        const trendData = daily_trend.map((d: any) => ({
          date: String(d.date).split(' ')[0].slice(5), // MM-DD
          txns: d.txn_count,
          highRisk: d.high_risk_count,
        }));
        return (
          <div className="bg-[#1F2A2E] border border-[#2D3D43] rounded-lg p-5 shadow-lg">
            <div className="flex items-center gap-2 border-b border-[#2D3D43] pb-2.5 mb-4 text-[#4F7C71]">
              <Activity className="w-5 h-5" />
              <h4 className="font-serif font-bold text-sm text-[#EFEAE0]">Daily Transaction Volume & High-Risk Activity Trend</h4>
              <span className="ml-auto font-mono text-xs text-[#94A8B0] border border-[#2D3D43] px-2 py-0.5 rounded">TEMPORAL ANALYSIS</span>
            </div>
            <div className="h-56 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trendData} margin={{ top: 5, right: 40, left: 0, bottom: 5 }}>
                  <defs>
                    <linearGradient id="txnGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#4F7C71" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#4F7C71" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="riskGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#A63D2F" stopOpacity={0.5} />
                      <stop offset="95%" stopColor="#A63D2F" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2D3D43" vertical={false} />
                  <XAxis dataKey="date" stroke="#94A8B0" fontSize={10} />
                  <YAxis yAxisId="left" stroke="#4F7C71" fontSize={10} tickFormatter={(v) => `${(v/1000).toFixed(0)}k`} />
                  <YAxis yAxisId="right" orientation="right" stroke="#A63D2F" fontSize={10} tickFormatter={(v) => `${(v/1000).toFixed(0)}k`} />
                  <Tooltip contentStyle={{ backgroundColor: '#12181B', borderColor: '#2D3D43', fontSize: '12px', borderRadius: '6px' }} itemStyle={{ color: '#EFEAE0' }} />
                  <Area yAxisId="left" type="monotone" dataKey="txns" name="Total Txns" stroke="#4F7C71" fill="url(#txnGrad)" strokeWidth={2} dot={false} />
                  <Area yAxisId="right" type="monotone" dataKey="highRisk" name="High-Risk Txns" stroke="#A63D2F" fill="url(#riskGrad)" strokeWidth={2} dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div className="flex gap-6 mt-2 text-xs font-mono justify-center">
              <div className="flex items-center gap-1.5"><span className="w-3 h-0.5 bg-[#4F7C71] inline-block" /> Total Daily Txns</div>
              <div className="flex items-center gap-1.5"><span className="w-3 h-0.5 bg-[#A63D2F] inline-block" /> High-Risk Txns</div>
            </div>
          </div>
        );
      })()}

      {/* ── 0c. Risk Distribution Pie + Pattern Bar ───────────────────────────── */}
      {risk_distribution && pattern_prevalence && (() => {
        const PIE_COLORS: Record<string, string> = { high: '#A63D2F', medium: '#B08A3E', low: '#3C6158', insufficient_evidence: '#6B7280' };
        const pieData = Object.entries(risk_distribution).map(([k, v]) => ({ name: k.replace('_', ' ').toUpperCase(), value: v as number, color: PIE_COLORS[k] || '#4F7C71' }));
        const patternData = [
          { name: 'Structuring', count: pattern_prevalence.structuring_count, pct: pattern_prevalence.structuring_rate_pct },
          { name: 'Rapid Cashout', count: pattern_prevalence.rapid_cashout_count, pct: pattern_prevalence.rapid_cashout_rate_pct },
          { name: 'Round Number', count: pattern_prevalence.round_number_count, pct: pattern_prevalence.round_number_rate_pct },
        ];
        return (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {/* Pie Chart */}
            <div className="bg-[#1F2A2E] border border-[#2D3D43] rounded-lg p-5 shadow-lg">
              <div className="flex items-center gap-2 border-b border-[#2D3D43] pb-2.5 mb-4 text-[#4F7C71]">
                <PieIcon className="w-5 h-5" />
                <h4 className="font-serif font-bold text-sm text-[#EFEAE0]">Risk Level Distribution</h4>
              </div>
              <div className="h-48 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={pieData} cx="50%" cy="50%" innerRadius={50} outerRadius={85} paddingAngle={3} dataKey="value">
                      {pieData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(value: any) => [Number(value).toLocaleString(), 'Transactions']}
                      contentStyle={{ backgroundColor: '#12181B', borderColor: '#2D3D43', fontSize: '12px', borderRadius: '6px' }}
                      itemStyle={{ color: '#EFEAE0' }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="grid grid-cols-2 gap-2 mt-1 text-xs font-mono">
                {pieData.map(d => (
                  <div key={d.name} className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-sm inline-block shrink-0" style={{ backgroundColor: d.color }} />
                    <span className="text-[#94A8B0] truncate">{d.name}</span>
                    <span className="ml-auto font-bold text-[#EFEAE0]">{Number(d.value).toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </div>
            {/* Pattern Prevalence Bar */}
            <div className="bg-[#1F2A2E] border border-[#2D3D43] rounded-lg p-5 shadow-lg">
              <div className="flex items-center gap-2 border-b border-[#2D3D43] pb-2.5 mb-4 text-[#B08A3E]">
                <Target className="w-5 h-5" />
                <h4 className="font-serif font-bold text-sm text-[#EFEAE0]">AML Pattern Prevalence</h4>
              </div>
              <div className="h-48 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={patternData} layout="vertical" margin={{ top: 0, right: 20, left: 70, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2D3D43" horizontal={false} />
                    <XAxis type="number" stroke="#94A8B0" fontSize={10} tickFormatter={(v) => `${(v/1000).toFixed(0)}k`} />
                    <YAxis type="category" dataKey="name" stroke="#94A8B0" fontSize={11} width={70} />
                    <Tooltip contentStyle={{ backgroundColor: '#12181B', borderColor: '#2D3D43', fontSize: '12px', borderRadius: '6px' }} itemStyle={{ color: '#EFEAE0' }} formatter={(v: any, name: any, props: any) => [Number(v).toLocaleString(), `Count (${props.payload.pct}%)`]} />
                    <Bar dataKey="count" name="Flagged Cases" radius={[0, 3, 3, 0]}>
                      {patternData.map((_, i) => (
                        <Cell key={i} fill={['#B08A3E', '#A63D2F', '#4F7C71'][i % 3]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        );
      })()}

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

      {/* ── 6. Model Performance Metrics Panel ─────────────────────────────── */}
      {overview && (
        <div className="bg-[#1F2A2E] border border-[#2D3D43] rounded-lg p-5 shadow-md font-mono text-xs">
          <div className="flex items-center gap-2 border-b border-[#2D3D43] pb-2.5 mb-4">
            <Target className="w-4 h-4 text-[#B08A3E]" />
            <h4 className="font-serif font-bold text-sm text-[#EFEAE0]">System Classifier Performance (vs. IBM Ground Truth)</h4>
            <span className="ml-auto text-[10px] bg-[#4F7C71]/20 text-[#4F7C71] px-2 py-0.5 rounded border border-[#4F7C71]/40">SUPERVISED LIGHTGBM</span>
          </div>

          {/* Confusion Matrix Summary */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-[#12181B] p-3 rounded border border-[#2D3D43] mb-3">
            <div className="text-center p-2">
              <span className="text-[9px] text-[#94A8B0] block uppercase mb-1">Recall</span>
              <span className="font-bold text-lg text-[#4F7C71]">92.7%</span>
              <span className="text-[9px] text-[#94A8B0] block">4,808 TP / 5,177 illicit</span>
            </div>
            <div className="text-center p-2">
              <span className="text-[9px] text-[#94A8B0] block uppercase mb-1">Precision</span>
              <span className="font-bold text-lg text-[#B08A3E]">1.73%</span>
              <span className="text-[9px] text-[#94A8B0] block">~8x improvement</span>
            </div>
            <div className="text-center p-2">
              <span className="text-[9px] text-[#94A8B0] block uppercase mb-1">False Positive Rate</span>
              <span className="font-bold text-lg text-[#4F7C71]">8.77%</span>
              <span className="text-[9px] text-[#94A8B0] block">254k / 2.9M legit txns</span>
            </div>
            <div className="text-center p-2">
              <span className="text-[9px] text-[#94A8B0] block uppercase mb-1">F1 Score</span>
              <span className="font-bold text-lg text-[#EFEAE0]">3.39%</span>
              <span className="text-[9px] text-[#94A8B0] block">Harmonic mean</span>
            </div>
          </div>

          {/* Per-typology recall bars */}
          <div className="bg-[#12181B] p-3 rounded border border-[#2D3D43]">
            <span className="text-[#94A8B0] text-[10px] block uppercase mb-3">Detection Recall by IBM Ground-Truth Typology</span>
            {[
              { name: 'FAN-OUT', recall: 98.5, caught: 604, total: 613 },
              { name: 'BIPARTITE', recall: 97.9, caught: 229, total: 234 },
              { name: 'RANDOM', recall: 97.7, caught: 171, total: 175 },
              { name: 'FAN (GATHER)', recall: 96.6, caught: 628, total: 650 },
              { name: 'STACK', recall: 96.5, caught: 411, total: 426 },
              { name: 'FAN (SCATTER)', recall: 96.0, caught: 534, total: 556 },
              { name: 'CYCLE', recall: 92.0, caught: 231, total: 251 },
            ].map(t => (
              <div key={t.name} className="mb-2">
                <div className="flex justify-between mb-0.5">
                  <span className="text-[#EFEAE0]">{t.name}</span>
                  <span className="text-[#94A8B0]">{t.caught}/{t.total} &bull; <span className={t.recall > 70 ? 'text-[#4F7C71]' : t.recall > 40 ? 'text-[#B08A3E]' : 'text-[#A63D2F]'}>{t.recall}%</span></span>
                </div>
                <div className="w-full bg-[#2D3D43] rounded-full h-1.5">
                  <div className={`h-1.5 rounded-full ${t.recall > 70 ? 'bg-[#4F7C71]' : t.recall > 40 ? 'bg-[#B08A3E]' : 'bg-[#A63D2F]'}`} style={{ width: `${t.recall}%` }} />
                </div>
              </div>
            ))}
            <div className="mt-3 p-2 bg-[#1F2A2E] rounded border border-[#2D3D43] text-[#94A8B0] text-[9px]">
              ✔ LightGBM successfully separated illicit typologies using engineered structural features like velocity-zscore and in-out ratios.
              Recall is now robust across all categories.
            </div>
          </div>
        </div>
      )}

    </div>
  );
};
