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
    method: 'UCSD QPASS survey workbooks and Parking Space Inventory reports, cleaned and matched to lots.',
    why: 'They are the only public counts. They mostly cover the first weeks of each quarter since 2018, with gaps.',
    status: 'Public sources',
  },
  {
    name: 'Forecast',
    method: 'The average open share for the same lot, weekday, time and quarter.',
    why: 'In our tests it beat a trained regression model on nearly full lots, and it is easy to explain.',
    status: LIVE ? 'Historical averages' : 'Prototype uses a sample curve. Real averages run in the hosted app.',
  },
  {
    name: 'Backend',
    method: 'A FastAPI service checks permit rules, attaches the forecast, scores and ranks lots.',
    why: 'One service means the website and a future app give the same answer.',
    status: LIVE ? 'Live on AWS' : 'Prototype uses sample data. Backend deploys on AWS next.',
  },
  {
    name: 'Routing',
    method: 'Walking and driving paths from OpenStreetMap-based routing, with any key kept on the server.',
    why: 'Real paths beat straight-line guesses, but the free public server is for light use only.',
    status: LIVE ? 'Off in this demo. Walk times are estimates; routing is planned.' : 'Prototype uses estimates. Routing is planned after the AWS demo.',
  },
  {
    name: 'This website',
    method: 'React and a MapLibre map that show a first choice and a backup.',
    why: 'The answer sits next to the map, so you can check it against where you are going.',
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
            <p className="pp-text"><span className="pp-label">What</span> {stage.method}</p>
            <p className="pp-text"><span className="pp-label">Why</span> {stage.why}</p>
            <span className="pp-status">{stage.status}</span>
          </li>
        ))}
      </ol>
      <p className="lp-note">
        {LIVE ? 'Hosted on AWS: Amplify, Lambda with API Gateway, and S3.' : 'Preview on sample data. The full app runs on AWS.'}
      </p>
    </div>
  );
};
