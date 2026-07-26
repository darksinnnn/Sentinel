import React, { useState, useRef } from 'react';
import { Search, Tag, ArrowRight, Filter, Layers, UserCheck, ShieldAlert, Upload } from 'lucide-react';

interface QueryBarProps {
  onSearch: (query: string) => void;
  onUpload: (file: File) => void;
  isLoading: boolean;
}

const CANONICAL_CHIPS = [
  { label: 'TARGETED: Structuring (30d)', query: 'Find structuring patterns in the last 30 days', icon: Filter },
  { label: 'AGGREGATION: 10+ Txns < $10k', query: 'Which customers made 10+ transactions under $10k?', icon: Layers },
  { label: 'LOOKUP: Account 8000EBD30', query: 'Is customer 8000EBD30 suspicious?', icon: UserCheck },
  { label: 'BROAD SCAN: Full Dataset Profiling', query: 'Analyze this entire dataset and give me top suspicious activities', icon: ShieldAlert },
];

export const QueryBar: React.FC<QueryBarProps> = ({ onSearch, onUpload, isLoading }) => {
  const [query, setQuery] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim() && !isLoading) {
      onSearch(query.trim());
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onUpload(e.target.files[0]);
    }
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleChipClick = (chipQuery: string) => {
    setQuery(chipQuery);
    onSearch(chipQuery);
  };

  return (
    <div className="w-full bg-[#1F2A2E] border border-[#2D3D43] rounded-lg p-4 shadow-lg mb-6">
      <form onSubmit={handleSubmit} className="flex gap-2 items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#94A8B0] w-4 h-4 pointer-events-none" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Enter natural language query or account ID (e.g. 'Find structuring patterns in last 30 days')..."
            className="w-full bg-[#12181B] border border-[#2D3D43] rounded-md pl-10 pr-4 py-2.5 text-sm text-[#EFEAE0] placeholder-[#94A8B0]/60 font-mono focus:outline-none focus-visible:ring-2 focus-visible:ring-[#4F7C71] focus-visible:border-transparent transition-all"
            disabled={isLoading}
          />
        </div>

        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={isLoading}
          className="bg-[#2D3D43] hover:bg-[#3C6158] text-white px-4 py-2.5 rounded-md font-sans text-sm font-semibold flex items-center gap-2 transition-all disabled:opacity-50 focus-visible:ring-2 focus-visible:ring-[#4F7C71] shadow-sm shrink-0"
          title="Upload Custom Data (.csv or .parquet)"
        >
          <Upload className="w-4 h-4" />
          <span className="hidden sm:inline">UPLOAD CSV</span>
        </button>
        <input 
          type="file" 
          ref={fileInputRef} 
          onChange={handleFileChange} 
          accept=".csv,.parquet" 
          className="hidden" 
        />

        <button
          type="submit"
          disabled={isLoading || !query.trim()}
          className="bg-[#4F7C71] hover:bg-[#64978B] active:bg-[#3C6158] text-white px-5 py-2.5 rounded-md font-sans text-sm font-semibold flex items-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-[#4F7C71] focus-visible:outline-none shadow-sm shrink-0"
        >
          <span>DISPATCH INQUIRY</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </form>

      {/* Structured Benchmark Case Tags */}
      <div className="mt-4">
        <span className="text-xs font-mono text-[#94A8B0] flex items-center gap-1.5 mb-2 uppercase">
          <Tag className="w-3.5 h-3.5 text-[#4F7C71]" /> Benchmark Cases:
        </span>
        <div className="flex flex-col gap-2">
          {CANONICAL_CHIPS.map((chip, idx) => {
          const IconComp = chip.icon;
          return (
            <button
              key={idx}
              type="button"
              onClick={() => handleChipClick(chip.query)}
              disabled={isLoading}
              className="bg-[#12181B] hover:bg-[#2D3D43] text-[#EFEAE0] hover:text-white text-xs font-mono px-3 py-1.5 rounded border border-[#2D3D43] transition-colors focus-visible:ring-2 focus-visible:ring-[#4F7C71] focus-visible:outline-none text-left flex items-center gap-1.5"
            >
              <IconComp className="w-3 h-3 text-[#4F7C71]" />
              <span>{chip.label}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};
