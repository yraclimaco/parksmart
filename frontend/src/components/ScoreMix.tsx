/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { DEFAULT_PRIORITY, PRIORITY_OPTIONS } from '../constants.ts';

/**
 * The scoring mix every search uses: the planner's real balanced weights. There is no switch
 * for it in the planner (priority and walk limit are fixed defaults), so this shows the one mix.
 */
export const ScoreMix: React.FC = () => {
  const option = PRIORITY_OPTIONS.find((o) => o.value === DEFAULT_PRIORITY) ?? PRIORITY_OPTIONS[1];
  const a = Math.round(option.availabilityWeight * 100);
  const w = Math.round(option.walkingWeight * 100);

  return (
    <div className="sm">
      <div className="sm-bar" role="img" aria-label={`${a} percent expected availability, ${w} percent walking convenience`}>
        <div className="sm-seg sm-seg--a" style={{ flexGrow: a, flexBasis: 0 }}>
          <span>{a}% availability</span>
        </div>
        <div className="sm-seg sm-seg--w" style={{ flexGrow: w, flexBasis: 0 }}>
          <span>{w}% walking</span>
        </div>
      </div>
      <p className="sm-note">Every search uses this mix.</p>
    </div>
  );
};
