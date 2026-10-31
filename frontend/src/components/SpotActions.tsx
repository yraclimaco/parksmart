/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { CheckCircle2, Navigation } from 'lucide-react';
import { googleMapsDirectionsUrl } from '../utils/mapsLink.ts';

interface SpotActionsProps {
  isConfirmed: boolean;
  disabled?: boolean;
  /** Visual weight: 'primary' (navy, lot card), 'subtle' (outlined, result cards) or 'onDark' (gold, on the navy first-choice card). */
  tone: 'primary' | 'subtle' | 'onDark';
  onConfirm: () => void;
  /** Where "Open in Google Maps" navigates to. */
  lot: { latitude: number; longitude: number };
}

/**
 * Two-step choice: "Select this spot" confirms the lot, then "Open in Google Maps" hands
 * off to Google Maps for turn-by-turn directions. "Your spot" undoes the confirmation.
 */
export const SpotActions: React.FC<SpotActionsProps> = ({
  isConfirmed,
  disabled = false,
  tone,
  onConfirm,
  lot,
}) => {
  const stop = (fn: () => void) => (e: React.MouseEvent) => {
    e.stopPropagation();
    fn();
  };
  const base =
    'flex items-center justify-center gap-1.5 py-2 rounded-lg text-[14px] font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-sky/40 cursor-pointer disabled:cursor-not-allowed disabled:opacity-50';

  if (!isConfirmed) {
    return (
      <button
        type="button"
        disabled={disabled}
        onClick={stop(onConfirm)}
        className={`w-full ${base} ${
          tone === 'primary'
            ? 'bg-navy text-white hover:bg-navy-2'
            : tone === 'onDark'
            ? 'bg-sun text-navy hover:bg-[#ffd633]'
            : 'bg-white border border-navy/30 text-navy hover:bg-paper'
        }`}
      >
        <CheckCircle2 className="w-4 h-4" aria-hidden="true" /> Select this spot
      </button>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        disabled={disabled}
        onClick={stop(onConfirm)}
        aria-label="Change your selected spot"
        className={`${base} px-3 ${
          tone === 'onDark' ? 'bg-white/15 text-white hover:bg-white/25' : 'bg-[#1E8E5A]/12 text-[#136B42] hover:bg-[#1E8E5A]/20'
        }`}
      >
        <CheckCircle2 className="w-4 h-4" aria-hidden="true" /> Your spot
      </button>
      <a
        href={googleMapsDirectionsUrl(lot.latitude, lot.longitude)}
        target="_blank"
        rel="noopener noreferrer"
        aria-disabled={disabled}
        onClick={(e) => {
          e.stopPropagation();
          if (disabled) e.preventDefault();
        }}
        className={`flex-1 ${base} ${
          tone === 'onDark' ? 'bg-sun text-navy hover:bg-[#ffd633]' : 'bg-navy text-white hover:bg-navy-2'
        } ${disabled ? 'pointer-events-none opacity-50' : ''}`}
      >
        <Navigation className="w-4 h-4" aria-hidden="true" /> Open in Google Maps
      </a>
    </div>
  );
};
