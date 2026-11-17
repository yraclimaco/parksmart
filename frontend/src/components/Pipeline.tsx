/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { RECOMMENDATION_SOURCE } from '../config';
import { LotCar, prefersReducedMotion, useInView } from './LotParts';

/** The hosted build talks to the AWS backend; other builds (previews) use labeled sample data. */
const LIVE = RECOMMENDATION_SOURCE === 'api';

/** Where a recommendation comes from, in order. Status says honestly how far along each part is. */
const STAGES = [
  {
    name: 'Public data',
    text: 'Past parking counts, lot sizes, and permit rules.',
    status: 'Public sources',
  },
  {
    name: 'Forecast',
    text: 'Typical open share by lot, weekday, and time of day.',
    status: LIVE ? 'Historical averages' : 'Sample curve here',
  },
  {
    name: 'Backend',
    text: 'A FastAPI service filters by permit, scores, and ranks.',
    status: LIVE ? 'Live on AWS' : 'Not connected here',
  },
  {
    name: 'Routing',
    text: 'Walking and driving paths from OpenStreetMap-based routing, with any key kept on the server.',
    status: LIVE ? 'Off in this demo; walks are estimates' : 'Not connected here',
  },
  {
    name: 'This website',
    text: 'React, TypeScript, and MapLibre. Shows a first choice and a backup.',
    status: 'You are here',
  },
] as const;

export const Pipeline: React.FC = () => {
  const [ref, seen] = useInView<HTMLDivElement>();
  const reduced = React.useMemo(prefersReducedMotion, []);
  const [active, setActive] = React.useState(reduced ? STAGES.length - 1 : 0);

  React.useEffect(() => {
    if (!seen || reduced) return;
    const id = window.setInterval(() => setActive((a) => (a + 1) % STAGES.length), 1700);
    return () => window.clearInterval(id);
  }, [seen, reduced]);

  return (
    <div className="pp" ref={ref}>
      <div className="pp-road" aria-hidden="true">
        <span className="pp-car" style={{ left: `calc(${(active / STAGES.length) * 100}% + 7px)` }}>
          <svg viewBox="-24 -30 48 60" width="30" height="38">
            <g transform="rotate(90)">
              <LotCar cx={0} cy={0} color="#FFCD00" />
            </g>
          </svg>
        </span>
      </div>
      <ol className="pp-stages">
        {STAGES.map((stage, i) => (
          <li key={stage.name} className={`pp-stage${i === active ? ' pp-stage--on' : ''}`}>
            <span className="pp-node" aria-hidden="true" />
            <h3 className="pp-name">{stage.name}</h3>
            <p className="pp-text">{stage.text}</p>
            <span className="pp-status">{stage.status}</span>
          </li>
        ))}
      </ol>
      <p className="lp-note">
        {LIVE
          ? 'Hosting: AWS Amplify serves the site, Lambda behind API Gateway runs the backend, and S3 holds the data files.'
          : 'Hosting: this preview uses sample data. The full app runs on AWS (Amplify, Lambda with API Gateway, and S3).'}
      </p>
    </div>
  );
};
