import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import type { RiskLevel } from '../types/outputContract';

interface VerdictStampProps {
  riskLevel: RiskLevel;
  className?: string;
}

export const VerdictStamp: React.FC<VerdictStampProps> = ({ riskLevel, className = '' }) => {
  const shouldReduceMotion = useReducedMotion();

  // Color & texture mappings based on exact design tokens
  const config = {
    high: {
      text: 'HIGH RISK',
      color: '#A63D2F', // Oxblood
      border: 'border-[#A63D2F]',
      textColor: 'text-[#A63D2F]',
      bg: 'bg-[#A63D2F]/10',
      rotation: '-2.5deg',
    },
    medium: {
      text: 'MEDIUM RISK',
      color: '#B08A3E', // Muted Brass
      border: 'border-[#B08A3E]',
      textColor: 'text-[#B08A3E]',
      bg: 'bg-[#B08A3E]/10',
      rotation: '3deg',
    },
    low: {
      text: 'LOW RISK',
      color: '#6B7280', // Quiet Slate
      border: 'border-[#6B7280]',
      textColor: 'text-[#6B7280]',
      bg: 'bg-[#6B7280]/10',
      rotation: '-1.5deg',
    },
    insufficient_evidence: {
      text: 'INSUFFICIENT EVIDENCE',
      color: '#8A8378', // Smudged Ghost
      border: 'border-[#8A8378]/60 border-dashed',
      textColor: 'text-[#8A8378]',
      bg: 'bg-[#8A8378]/15 stamp-smudged-texture',
      rotation: '4deg',
    },
  }[riskLevel] || {
    text: riskLevel.toUpperCase(),
    color: '#6B7280',
    border: 'border-[#6B7280]',
    textColor: 'text-[#6B7280]',
    bg: 'bg-[#6B7280]/10',
    rotation: '0deg',
  };

  const initialProps = shouldReduceMotion
    ? { scale: 1, opacity: 1, rotate: config.rotation }
    : { scale: 1.8, opacity: 0, rotate: '0deg' };

  const animateProps = {
    scale: 1,
    opacity: 1,
    rotate: config.rotation,
  };

  return (
    <motion.div
      initial={initialProps}
      animate={animateProps}
      transition={{
        type: 'spring',
        stiffness: 300,
        damping: 18,
      }}
      className={`inline-flex items-center justify-center select-none ${className}`}
    >
      <div
        className={`px-3 py-1 border-2 rounded ${config.border} ${config.bg} shadow-sm backdrop-blur-[1px] relative overflow-hidden`}
        style={{ transform: `rotate(${config.rotation})` }}
      >
        {/* Hairline inner border for physical stamp effect */}
        <div className={`absolute inset-[2px] border ${config.border} rounded-sm opacity-60 pointer-events-none`} />
        <span className={`font-mono font-bold tracking-wider text-xs sm:text-sm uppercase ${config.textColor}`}>
          {config.text}
        </span>
      </div>
    </motion.div>
  );
};
