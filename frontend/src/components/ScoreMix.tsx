/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { PRIORITY_OPTIONS } from '../constants.ts';

const NOTES: Record<string, string> = {
  shorter_walk: 'Closer parking, even if it is usually fuller.',
  balanced: 'The default mix.',
  more_availability: 'More open spaces, even if it is a longer walk.',
};

/** Shows the real scoring weights from the planner and how each priority shifts them. */
export const ScoreMix: React.FC = () => {
  const [value, setValue] = React.useState('balanced');
  const option = PRIORITY_OPTIONS.find((o) => o.value === value) ?? PRIORITY_OPTIONS[1];
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
      <p className="sm-note">{NOTES[value]}</p>
      <div className="sm-buttons" role="group" aria-label="Priority">
        {PRIORITY_OPTIONS.map((o) => (
          <button
            key={o.value}
            type="button"
            className={`sm-btn${o.value === value ? ' sm-btn--on' : ''}`}
            aria-pressed={o.value === value}
            onClick={() => setValue(o.value)}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
};
