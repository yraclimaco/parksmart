/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { LotCar, prefersReducedMotion, useInView } from './LotParts';

/** Where a recommendation comes from, in order, as it runs today. Status says how far along each part is. */
const STAGES = [
  {
    name: 'Public data',
    method: 'UCSD QPASS survey workbooks and Parking Space Inventory reports, cleaned into 76,102 readings and matched to campus lots and structures.',
    why: 'They are UCSD\'s own counts. They come from the first two weeks of each quarter, which represent the whole quarter.',
    status: 'June 2018 to October 2026',
  },
  {
    name: 'Forecast',
    method: 'The average open share for the same lot, weekday, time and quarter, loaded once when the server starts.',
    why: 'In our tests it beat a trained regression model on nearly full lots, and it is easy to explain.',
    status: 'Historical averages',
  },
  {
    name: 'Backend',
    method: 'A FastAPI service checks your permit\'s rules for your arrival, drops lots over a 20-minute walk, scores the rest, and adds weather and construction notes.',
    why: 'One service means the website and the iOS app being built give the same answer.',
    status: 'Live on AWS',
  },
  {
    name: 'Routing',
    method: 'Walking and driving routes from OpenStreetMap-based routing, with any key kept on the server.',
    why: 'Real paths beat straight-line guesses. Until a routing server is set up, walk times are straight-line estimates.',
    status: 'Built, off in the hosted demo',
  },
  {
    name: 'This website',
    method: 'React and a MapLibre map. Import your class schedule and each class gets a first choice and a backup.',
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
        Hosted on AWS: Amplify, Lambda with API Gateway, and S3.
      </p>
    </div>
  );
};
