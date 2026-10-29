/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { motion } from 'motion/react';
import { availabilityStatus } from '../utils/availability.ts';

interface AvailabilityMeterProps {
  percent: number;
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
export const AvailabilityMeter: React.FC<AvailabilityMeterProps> = ({
  percent,
  timeLabel,
  tone = 'light',
  size = 'md',
}) => {
  const status = availabilityStatus(percent);
  const dark = tone === 'dark';

  return (
    <div>
      <div className="flex items-end justify-between gap-2">
        <div>
          <div
            className={`font-serif font-semibold tabular-nums leading-none ${
              size === 'lg' ? 'text-[36px]' : 'text-[28px]'
            } ${dark ? 'text-sun' : 'text-navy'}`}
          >
            {percent}%
            <span className={`ml-1.5 font-sans text-[13px] font-medium ${dark ? 'text-white/70' : 'text-muted'}`}>open</span>
          </div>
          <div className={`mt-1 text-xs ${dark ? 'text-white/70' : 'text-muted'}`}>Estimated for {timeLabel}</div>
        </div>
        <span
          className="px-2.5 py-1 rounded-md text-[13px] font-semibold"
          style={
            dark
              ? { color: '#fff', backgroundColor: 'rgba(255,255,255,0.14)' }
              : { color: status.textColor, backgroundColor: `${status.color}26` }
          }
        >
          {status.label}
        </span>
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
