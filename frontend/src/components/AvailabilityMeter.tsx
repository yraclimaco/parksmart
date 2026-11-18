/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { motion } from 'motion/react';
import { availabilityStatus } from '../utils/availability.ts';

interface AvailabilityMeterProps {
  /** null when there is no estimate: shown as "Unavailable", never 0%. */
  percent: number | null;
  /** "10:30 AM", the time the estimate describes. */
  timeLabel: string;
  /** "dark" for the navy first-choice card. */
  tone?: 'light' | 'dark';
  size?: 'md' | 'lg';
}

/**
 * The one availability readout: big percent, status chip, bar and the time it describes.
 * Result cards and the map's lot card both render this, so the same lot never reads
 * differently depending on where you look.
 */
/** Past-survey averages near 100% still are not a guarantee, so they read "95%+". */
const CAP_AT = 95;

export const AvailabilityMeter: React.FC<AvailabilityMeterProps> = ({
  percent,
  timeLabel,
  tone = 'light',
  size = 'md',
}) => {
  const dark = tone === 'dark';
  if (percent === null) {
    return (
      <div>
        <div className={`font-serif font-semibold leading-none ${size === 'lg' ? 'text-[28px]' : 'text-[22px]'} ${dark ? 'text-white' : 'text-navy'}`}>
          Unavailable
        </div>
        <div className={`mt-1 text-xs ${dark ? 'text-white/70' : 'text-muted'}`}>No estimate for {timeLabel}</div>
      </div>
    );
  }
  const status = availabilityStatus(percent);

  return (
    <div>
      <div className="flex items-end justify-between gap-2">
        <div>
          {/* The word leads: the number is a historical average, not a count of free stalls */}
          <div
            className={`font-serif font-semibold leading-none ${
              size === 'lg' ? 'text-[30px]' : 'text-[24px]'
            } ${dark ? 'text-sun' : 'text-navy'}`}
          >
            {status.label}
          </div>
          <div className={`mt-1.5 text-[13px] ${dark ? 'text-white/80' : 'text-muted'}`}>
            <span className="tabular-nums font-semibold">{percent >= CAP_AT ? `${CAP_AT}%+` : `about ${percent}%`}</span> open in past
            surveys for {timeLabel}
          </div>
        </div>
      </div>
      <div className={`mt-2.5 h-2 rounded-full overflow-hidden ${dark ? 'bg-white/20' : 'bg-paper'}`}>
        <motion.div
          className="h-full rounded-full"
          style={{ backgroundColor: status.color }}
          initial={{ width: 0 }}
          animate={{ width: `${percent}%` }}
          transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
        />
      </div>
    </div>
  );
};
