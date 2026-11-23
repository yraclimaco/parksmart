/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { useInView } from './LotParts';

/**
 * Screen 2's picture: the filters ParkSmart applies, from every campus lot down to one pick and a
 * backup. Each band is narrower than the one above it. No counts: they would depend on the search.
 */
const STAGES = [
  { label: 'Every campus lot', note: 'Where other parking apps stop' },
  { label: 'Your permit', note: 'Only stalls you can legally use' },
  { label: 'Near your class', note: 'A short walk to your building' },
  { label: 'Arrive on time', note: 'Parked and walking in before class starts' },
] as const;

export const WhyFunnel: React.FC = () => {
  const [ref, inView] = useInView<HTMLOListElement>();
  return (
    <ol ref={ref} className={`wf-list${inView ? ' wf-list--in' : ''}`} aria-label="How ParkSmart narrows your options">
      {STAGES.map((s, i) => (
        <li key={s.label} className="wf-stage" style={{ '--wf-i': i } as React.CSSProperties}>
          <strong>{s.label}</strong>
          <span>{s.note}</span>
        </li>
      ))}
      <li className="wf-stage wf-stage--result" style={{ '--wf-i': STAGES.length } as React.CSSProperties}>
        <strong>First choice + backup</strong>
        <span>For every class, before you leave</span>
      </li>
    </ol>
  );
};
