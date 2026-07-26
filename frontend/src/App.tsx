import { useState } from 'react';
import { Shield, PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen, AlertCircle, CheckCircle2, ShieldCheck, FileCheck, Layers, Download } from 'lucide-react';
import { QueryBar } from './components/QueryBar';
import { ExecutionSummaryPanel } from './components/ExecutionSummaryPanel';
import { EvidenceCard } from './components/EvidenceCard';
import { TracePanel } from './components/TracePanel';
import { CaseLog } from './components/CaseLog';
import { SupportingMetrics } from './components/SupportingMetrics';
import { SystemOverview } from './components/SystemOverview';
import type { AgentResponse } from './types/outputContract';
import { sendQuery } from './api/sentinel';

interface HistoryItem {
  query: string;
  auditRef: string;
  timestamp: string;
  flaggedCount: number;
}

export function App() {
  const [currentResponse, setCurrentResponse] = useState<AgentResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [showLeftSidebar, setShowLeftSidebar] = useState(true);
  const [showRightSidebar, setShowRightSidebar] = useState(true);
  const [showOverview, setShowOverview] = useState(false);

  const handleSearch = async (queryText: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await sendQuery(queryText);
      setCurrentResponse(response);

      // Append to case history log
      const newHistoryItem: HistoryItem = {
        query: queryText,
        auditRef: response.audit_ref,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        flaggedCount: response.flagged_items.length,
      };
      setHistory((prev) => [newHistoryItem, ...prev]);
    } catch (err: any) {
      setError(err.message || 'An error occurred while dispatching query to Sentinel API.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpload = async (file: File) => {
    setIsLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const res = await fetch('http://localhost:8000/api/v1/analyze-custom', {
        method: 'POST',
        body: formData,
      });
      
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to upload and analyze custom data.');
      }
      
      const response = await res.json();
      setCurrentResponse(response);

      const newHistoryItem: HistoryItem = {
        query: `Custom Upload: ${file.name}`,
        auditRef: response.audit_ref,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        flaggedCount: response.flagged_items.length,
      };
      setHistory((prev) => [newHistoryItem, ...prev]);
    } catch (err: any) {
      setError(err.message || 'An error occurred during custom upload.');
    } finally {
      setIsLoading(false);
    }
  };

  const exportQueryReport = () => {
    if (!currentResponse) return;
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(currentResponse, null, 2));
    const downloadAnchorNode = document.createElement('a');
    downloadAnchorNode.setAttribute("href", dataStr);
    downloadAnchorNode.setAttribute("download", `sentinel_query_report_${currentResponse.audit_ref}.json`);
    document.body.appendChild(downloadAnchorNode);
    downloadAnchorNode.click();
    downloadAnchorNode.remove();
  };

  return (
    <div className="flex flex-col h-screen bg-[#12181B] text-[#EFEAE0] overflow-hidden selection:bg-[#4F7C71] selection:text-white font-sans">
      {/* Top Header Bar */}
      <header className="h-14 bg-[#1F2A2E] border-b border-[#2D3D43] px-4 flex items-center justify-between shrink-0 z-10 shadow-md">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowLeftSidebar(!showLeftSidebar)}
            className="text-[#94A8B0] hover:text-[#EFEAE0] p-1.5 rounded hover:bg-[#12181B] transition-colors focus-visible:ring-2 focus-visible:ring-[#4F7C71] focus-visible:outline-none"
            title="Toggle Case Log Sidebar"
          >
            {showLeftSidebar ? <PanelLeftClose className="w-4 h-4" /> : <PanelLeftOpen className="w-4 h-4" />}
          </button>

          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded bg-[#4F7C71]/20 border border-[#4F7C71] flex items-center justify-center text-[#4F7C71]">
              <Shield className="w-4 h-4" />
            </div>
            <div>
              <h1 className="font-sans font-bold text-sm tracking-wide text-[#EFEAE0] uppercase">
                Sentinel <span className="text-xs text-[#94A8B0] font-normal lowercase">| Investigation Workbench</span>
              </h1>
              <span className="font-mono text-[10px] text-[#4F7C71] block tracking-tight">
                Auditable Risk Intelligence & Tool Orchestration Engine
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 font-mono text-xs">
          <span className="hidden sm:inline-flex items-center gap-1.5 bg-[#12181B] px-2.5 py-1 rounded border border-[#2D3D43] text-[#64978B]">
            <span className="w-2 h-2 rounded-full bg-[#4F7C71] animate-pulse" />
            API STATUS: 127.0.0.1:8000
          </span>

          <div className="flex items-center gap-3">
          <button 
            onClick={() => setShowOverview(!showOverview)}
            className={`font-sans text-xs font-bold uppercase tracking-wider px-3 py-1.5 rounded transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4F7C71] ${showOverview ? 'bg-[#4F7C71] text-white shadow-[0_0_15px_rgba(79,124,113,0.3)]' : 'bg-transparent text-[#94A8B0] hover:text-[#EFEAE0] hover:bg-[#2D3D43]'}`}
          >
            Architecture & Metrics
          </button>
          
          <button 
            onClick={() => setShowRightSidebar(!showRightSidebar)}
            className="text-[#94A8B0] hover:text-[#EFEAE0] transition-colors p-1 rounded hover:bg-[#2D3D43] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4F7C71]"
            title="Toggle Audit Trace Panel"
          >
            {showRightSidebar ? <PanelRightClose className="w-5 h-5" /> : <PanelRightOpen className="w-5 h-5" />}
          </button>
        </div>
        </div>
      </header>

      {/* Main Three-Pane Body */}
      <div className="flex-1 flex flex-col lg:flex-row overflow-hidden relative">
        {/* Left Pane: Case Log */}
        {showLeftSidebar && (
          <CaseLog history={history} onSelectQuery={handleSearch} />
        )}

        {/* Center Pane: The Desk */}
        <div className="flex flex-1 overflow-hidden relative">
        {/* Main Content Area: Analysis Desk or System Overview */}
        <div className={`flex-1 overflow-y-auto ${showRightSidebar ? 'pr-0 border-r border-[#2D3D43]' : ''} transition-all duration-300 relative scroll-smooth`}>
          <div className="max-w-5xl mx-auto p-8 relative min-h-full">
            {showOverview ? (
              <SystemOverview />
            ) : (
              <div className="flex flex-col gap-6 relative z-10">
                {/* ── Query Bar ────────────────────────────────────────────── */}
                <QueryBar 
                  onSearch={handleSearch} 
                  onUpload={handleUpload}
                  isLoading={isLoading} 
                />

            {/* Error Notification */}
            {error && (
              <div className="bg-[#A63D2F]/15 border border-[#A63D2F]/50 text-[#EFEAE0] p-4 rounded-lg mb-6 flex items-start gap-3 shadow-md font-mono text-xs">
                <AlertCircle className="w-5 h-5 text-[#A63D2F] shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold text-[#A63D2F] block mb-0.5">FastAPI Backend Connection Error</span>
                  <p className="text-[#EFEAE0]/90">{error}</p>
                  <span className="text-[10px] text-[#94A8B0] block mt-2">
                    Ensure Uvicorn server is running: `uvicorn src.api.app:app --port 8000`
                  </span>
                </div>
              </div>
            )}

            {/* Loading Indicator — Case File Procedural Progress */}
            {isLoading && (
              <div className="bg-[#1F2A2E] border border-[#4F7C71]/40 rounded-lg p-6 my-8 shadow-lg font-mono text-xs text-[#EFEAE0]">
                <div className="flex items-center justify-between mb-3 border-b border-[#2D3D43] pb-2">
                  <span className="text-[#4F7C71] font-bold tracking-wider flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-[#4F7C71] animate-ping" />
                    FORENSIC INQUIRY IN PROGRESS
                  </span>
                  <span className="text-[#94A8B0] text-[10px]">EXECUTION_ID: DISPATCHING</span>
                </div>
                <p className="text-[#D8E2E6] mb-3">
                  Inspecting transaction records → Routing tools → Evaluating risk tiers → Synthesizing evidence
                </p>
                <div className="w-full bg-[#12181B] h-1.5 rounded-full overflow-hidden border border-[#2D3D43]">
                  <div className="bg-[#4F7C71] h-full animate-pulse w-3/4 rounded-full" />
                </div>
              </div>
            )}

            {/* Empty State / Initial Load */}
            {!currentResponse && !isLoading && !error && (
              <div className="bg-[#1F2A2E]/50 border border-[#2D3D43] rounded-lg p-10 text-center my-6 shadow-inner">
                <Shield className="w-12 h-12 text-[#4F7C71] opacity-40 mx-auto mb-4" />
                <h2 className="font-sans text-lg text-[#EFEAE0] font-bold mb-2 uppercase tracking-wide">
                  Ready for Forensic Inquiry
                </h2>
                <p className="font-sans text-sm text-[#94A8B0] max-w-lg mx-auto mb-6 leading-relaxed">
                  Select a benchmark case tag above or enter a natural language prompt to trigger dynamic tool orchestration over 2.87M scored transactions.
                </p>
                <div className="inline-flex flex-wrap justify-center items-center gap-4 text-xs font-mono text-[#64978B] bg-[#12181B] px-4 py-2 rounded-full border border-[#2D3D43]">
                  <span className="flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-[#4F7C71]" /> SHA-256 Hash Chained
                  </span>
                  <span>·</span>
                  <span className="flex items-center gap-1.5">
                    <ShieldCheck className="w-3.5 h-3.5 text-[#4F7C71]" /> Rule-Gated Tiers
                  </span>
                  <span>·</span>
                  <span className="flex items-center gap-1.5">
                    <FileCheck className="w-3.5 h-3.5 text-[#4F7C71]" /> Auto SAR Generation
                  </span>
                </div>
              </div>
            )}

            {/* Response Section */}
            {currentResponse && !isLoading && (
              <div>
                {/* Execution Summary Checklist */}
                <ExecutionSummaryPanel summary={currentResponse.execution_summary} />

                {/* Supporting Metrics Charts */}
                {currentResponse.supporting_metrics && (
                  <SupportingMetrics metrics={currentResponse.supporting_metrics} />
                )}

                {/* Evidence Cards Stack Header */}
                <div className="mb-4 flex items-center justify-between border-b border-[#2D3D43] pb-2">
                  <h3 className="font-sans font-bold text-base text-[#EFEAE0] uppercase tracking-wider flex items-center gap-2">
                    <Layers className="w-4 h-4 text-[#4F7C71]" />
                    <span>Evidence Cards & Findings</span>
                    <span className="font-mono text-xs font-normal bg-[#4F7C71]/20 text-[#64978B] px-2 py-0.5 rounded border border-[#4F7C71]/40">
                      {currentResponse.flagged_items.length} items flagged
                    </span>
                  </h3>
                  <div className="flex items-center gap-3">
                    <button 
                      onClick={exportQueryReport}
                      className="flex items-center gap-1.5 font-mono text-xs text-[#94A8B0] hover:text-[#EFEAE0] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4F7C71] rounded px-1"
                    >
                      <Download className="w-3.5 h-3.5" />
                      Export Query
                    </button>
                    <span className="font-mono text-xs text-[#94A8B0]">
                      Audit Ref: <strong className="text-[#4F7C71]">{currentResponse.audit_ref}</strong>
                    </span>
                  </div>
                </div>

                {currentResponse.flagged_items.length === 0 ? (
                  <div className="bg-[#1F2A2E] p-6 rounded-lg border border-[#2D3D43] text-center font-mono text-xs text-[#94A8B0]">
                    No suspicious items met flagged risk thresholds for this specific inquiry.
                  </div>
                ) : (
                  currentResponse.flagged_items.map((item, idx) => (
                    <EvidenceCard key={`${item.entity_id}-${idx}`} item={item} index={idx} />
                  ))
                )}
              </div>
            )}
            
              </div>
            )}
          </div>
        </div>

        {/* Right Pane: Execution & Audit Trace */}
        {showRightSidebar && (
          <TracePanel
            summary={currentResponse?.execution_summary || null}
            auditRef={currentResponse?.audit_ref || null}
          />
        )}
      </div>
      </div>
    </div>
  );
}

export default App;
