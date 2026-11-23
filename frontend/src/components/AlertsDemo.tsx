/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { CloudSun, Construction } from 'lucide-react';
import { NEARBY_DISTANCE_TEXT } from '../utils/alertFormat';

/**
 * Screen 6's picture: what a result shows beside its availability, the forecast for the arrival
 * time and any UCSD construction notices near the trip, marked as not changing the score.
 * Example values only.
 */
export const AlertsDemo: React.FC = () => (
  <div className="ad">
    <div className="ad-card" role="group" aria-label="Example result with weather and construction">
      <p className="ad-top">
        <span className="ad-tag">First choice</span>
        <strong>Lot P503</strong>
        <span>about 82% open in past surveys for 9:00 AM</span>
      </p>

      <div className="ad-row">
        <CloudSun className="ad-icon" aria-hidden="true" />
        <div>
          <p className="ad-label">Weather at 9:00 AM</p>
          <p className="ad-text">62°F (feels like 60°F), wind 6 mph, 10% chance of rain</p>
        </div>
      </div>

      <div className="ad-row">
        <Construction className="ad-icon" aria-hidden="true" />
        <div>
          <p className="ad-label">
            Construction <span className="ad-pill">Within {NEARBY_DISTANCE_TEXT}</span>
          </p>
          <p className="ad-text">Lane closure on a road near the lot, active at your arrival time</p>
        </div>
      </div>

      <p className="ad-honest">Notes only. They never change a lot&apos;s score or hide it.</p>
    </div>
  </div>
);
