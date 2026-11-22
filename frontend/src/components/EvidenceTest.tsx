/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { useInView } from './LotParts';

/**
 * The evidence screen: how the forecast was tested and what the test found, written for someone who
 * has never used ParkSmart. Figures are the supported holdout results in docs/issue18_predictions.md
 * (backend repo): 11,665 readings, 21.047 pp mean absolute error, 13.729 pp when nearly full
 * (10% or less open), and 4,458 readings with no supported estimate. The holdout starts 2025-10-08.
 */
const STEPS = [
  {
    name: 'Set aside recent counts',
    text: 'We held back UCSD’s most recent hand counts of open spaces, from October 2025 on, so ParkSmart could not use them.',
  },
  {
    name: 'Forecast them',
    text: 'ParkSmart forecast those same lots, days and times using only older surveys, exactly the way it forecasts your trip.',
  },
  {
    name: 'Compare',
    text: 'We compared every forecast with what UCSD’s surveyors actually counted, 11,665 counts in all.',
  },
] as const;

export const EvidenceTest: React.FC<{ heading: React.ReactNode }> = ({
  heading,
}) => {
  const [ref, inView] = useInView<HTMLOListElement>();
  return (
    <div className="et">
      <div className="et-head">
        {heading}
        <p className="et-intro">
          ParkSmart forecasts what share of a lot&apos;s spaces is usually open,
          like &ldquo;60% open.&rdquo; To check those forecasts fairly, we
          tested them on real counts ParkSmart had never seen, the same
          situation as forecasting a day that has not happened yet.
        </p>
      </div>

      <ol
        ref={ref}
        className={`et-steps${inView ? ' et-steps--in' : ''}`}
        aria-label="How the forecast was tested"
      >
        {STEPS.map((s, i) => (
          <li
            key={s.name}
            className="et-step"
            style={{ '--et-i': i } as React.CSSProperties}
          >
            <span className="et-num" aria-hidden="true">
              {i + 1}
            </span>
            <strong>{s.name}</strong>
            <span>{s.text}</span>
          </li>
        ))}
      </ol>

      <div className="et-bottom">
        <div className="et-result">
          <p className="et-big">
            Off by 21% <span>on average</span>
          </p>
          <p className="et-explain">
            That is 21% of a lot&apos;s spaces. So when ParkSmart said a lot was
            60% open, the real count was typically somewhere around 40% to 80%.
          </p>
        </div>

        <div className="et-side">
          <ul className="et-facts">
            <li>
              <strong>Closer for full lots.</strong> When a lot really was
              nearly full (10% or fewer spaces open), forecasts were off by 14%
              on average.
            </li>
            <li>
              <strong>No guessing.</strong> For 4,458 counts, ParkSmart had no
              past surveys of that lot at that time, so it showed no forecast at
              all instead of making one up.
            </li>
          </ul>

          <p className="et-takeaway">
            What it means for you: a result is a useful guide to which lots
            usually have room, not a promise of a space.
          </p>
        </div>
      </div>
    </div>
  );
};
