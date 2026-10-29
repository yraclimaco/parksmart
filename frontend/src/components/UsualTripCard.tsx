/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { motion } from 'motion/react';
import { Repeat } from 'lucide-react';
import { ParkingRecommendation } from '../types.ts';
import { availabilityStatus } from '../utils/availability.ts';

interface UsualTripCardProps {
  destinationName: string;
  /** e.g. "Thu 9:40 AM" */
  whenLabel: string;
  /** Best pick for the usual trip, computed instantly; null if nothing fits. */
  topPick: ParkingRecommendation | null;
  /** e.g. "9:45 AM": when the top pick usually gets tight that day. */
  tightAt: string | null;
  onShowOptions: () => void;
  onForget: () => void;
}

/**
 * Zero-tap answer for returning users: their usual trip, already solved.
 * Saved only in this browser (see utils/usualTrip.ts).
 */
export const UsualTripCard: React.FC<UsualTripCardProps> = ({
  destinationName,
  whenLabel,
  topPick,
  tightAt,
  onShowOptions,
  onForget,
}) => {
  const status = topPick ? availabilityStatus(topPick.lot.estimatedAvailabilityPercent) : null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
      className="p-4 rounded-2xl bg-white border border-line shadow-[0_4px_12px_rgba(24,43,73,0.1)]"
    >
      <div className="flex items-center gap-1.5 text-[13px] font-semibold text-muted">
        <Repeat className="w-3.5 h-3.5" aria-hidden="true" /> Your usual
      </div>
      <p className="mt-1.5 text-[15px] font-bold leading-snug text-navy">
        Heading to {destinationName}, {whenLabel}?
      </p>

      {topPick && status ? (
        <>
          <div className="mt-3 flex items-center justify-between gap-2">
            <span className="text-sm font-semibold text-navy truncate">{topPick.lot.name}</span>
            <span
              className="shrink-0 px-2 py-0.5 rounded-full text-[12px] font-semibold"
              style={{ color: status.textColor, backgroundColor: `${status.color}26` }}
            >
              {topPick.lot.estimatedAvailabilityPercent}% · {status.label}
            </span>
          </div>
          <p className="mt-1.5 text-[12px] text-muted">
            {tightAt ? `It usually gets tight around ${tightAt}. Arrive before then.` : 'It usually stays open all day.'}
          </p>
        </>
      ) : (
        <p className="mt-2 text-[12px] text-muted">Nothing fits your permit at that time. Try another time.</p>
      )}

      <button
        type="button"
        onClick={onShowOptions}
        className="mt-3 w-full py-2.5 rounded-xl bg-navy hover:bg-navy-2 text-white text-[13px] font-semibold transition-colors cursor-pointer"
      >
        Show my options
      </button>
      <button
        type="button"
        onClick={onForget}
        className="mt-1.5 w-full py-1 text-[11px] font-medium text-muted hover:text-navy cursor-pointer"
      >
        Forget my usual (saved only on this device)
      </button>
    </motion.div>
  );
};
