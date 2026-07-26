import React from 'react';
import { FolderArchive, FileText, History } from 'lucide-react';

interface HistoryItem {
  query: string;
  auditRef: string;
  timestamp: string;
  flaggedCount: number;
}

interface CaseLogProps {
  history: HistoryItem[];
  onSelectQuery: (query: string) => void;
}

export const CaseLog: React.FC<CaseLogProps> = ({ history, onSelectQuery }) => {
  return (
    <aside className="w-full lg:w-72 bg-[#12181B] border-b lg:border-b-0 lg:border-r border-[#2D3D43] p-4 flex flex-col h-full overflow-y-auto text-xs text-[#EFEAE0]">
      <div className="flex items-center gap-2 border-b border-[#2D3D43] pb-3 mb-4">
        <FolderArchive className="w-4 h-4 text-[#4F7C71]" />
        <h3 className="font-serif font-semibold text-base text-[#EFEAE0]">Case Log & History</h3>
      </div>

      {history.length === 0 ? (
        <div className="text-center py-10 text-[#94A8B0]/60 font-mono text-xs">
          <History className="w-8 h-8 mx-auto mb-2 opacity-30" />
          No prior cases logged in current session.
        </div>
      ) : (
        <div className="space-y-2.5">
          <span className="font-mono text-[#94A8B0] uppercase text-[10px] tracking-wider block mb-2">
            Active Session Case Index ({history.length})
          </span>
          {history.map((item, idx) => (
            <button
              key={idx}
              onClick={() => onSelectQuery(item.query)}
              className="w-full bg-[#1F2A2E] hover:bg-[#222C31] p-3 rounded border border-[#2D3D43] hover:border-[#4F7C71]/50 text-left transition-all focus-visible:ring-2 focus-visible:ring-[#4F7C71] focus-visible:outline-none"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-mono text-[10px] text-[#4F7C71] flex items-center gap-1">
                  <FileText className="w-3 h-3" /> {item.auditRef}
                </span>
                <span className="font-mono text-[10px] text-[#94A8B0]">{item.timestamp}</span>
              </div>
              <p className="font-sans text-xs text-[#EFEAE0] line-clamp-2 font-medium">
                "{item.query}"
              </p>
              <span className="font-mono text-[10px] text-[#B08A3E] mt-1.5 inline-block">
                {item.flaggedCount} item{item.flaggedCount === 1 ? '' : 's'} flagged
              </span>
            </button>
          ))}
        </div>
      )}
    </aside>
  );
};
