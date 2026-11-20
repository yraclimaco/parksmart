/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { Navigation } from 'lucide-react';
import { googleMapsDirectionsUrl } from '../utils/mapsLink.ts';

interface SpotActionsProps {
  /** True when this lot is already the selected one. */
  isSelected: boolean;
  disabled?: boolean;
  /** Visual weight: 'primary' (navy, lot card), 'subtle' (outlined, result cards) or 'onDark' (gold, on the navy first-choice card). */
  tone: 'primary' | 'subtle' | 'onDark';
  /** Chooses this lot (card, map pin and route). Called when directions are opened and it is not selected yet. */
  onChoose: () => void;
  /** Where "Open in Google Maps" navigates to. */
  lot: { latitude: number; longitude: number };
}

/**
 * One tap to go: "Open in Google Maps" hands off to turn-by-turn directions, and also
 * selects the lot so the highlighted card, the map pin and the route match what was opened.
 */
export const SpotActions: React.FC<SpotActionsProps> = ({
  isSelected,
  disabled = false,
  tone,
  onChoose,
  lot,
}) => {
  const base =
    'flex items-center justify-center gap-1.5 py-2 max-sm:min-h-[44px] rounded-lg text-[14px] font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-sky cursor-pointer';

  return (
    <a
      href={googleMapsDirectionsUrl(lot.latitude, lot.longitude)}
      target="_blank"
      rel="noopener noreferrer"
      aria-disabled={disabled}
      onClick={(e) => {
        e.stopPropagation();
        if (disabled) {
          e.preventDefault();
          return;
        }
        if (!isSelected) onChoose();
      }}
      className={`w-full ${base} ${
        tone === 'primary'
          ? 'bg-navy text-white hover:bg-navy-2'
          : tone === 'onDark'
          ? 'bg-sun text-navy hover:bg-[#ffd633]'
          : 'bg-white border border-navy/30 text-navy hover:bg-paper'
      } ${disabled ? 'pointer-events-none opacity-50' : ''}`}
    >
      <Navigation className="w-4 h-4" aria-hidden="true" /> Open in Google Maps
    </a>
  );
};
