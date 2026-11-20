/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { LotCar } from './LotParts';

const STALL_X = [40, 110, 180, 250];
/** The stalls run from x=40 to x=320, so shifting the lot left by half the difference puts equal margins on both sides of the 320-wide box. */
const LOT_SHIFT_X = -20;
const PARKED = [0, 1, 3];
const PARKED_COLORS = ['#7C93B5', '#F7F8FA', '#4A6690'];

const Scene: React.FC = () => (
  <svg className="ml-scene" viewBox="0 0 320 220" aria-hidden="true">
    <rect width="320" height="220" rx="18" fill="#101D33" />
    {/* The lane line is already centered in the box */}
    <line x1="10" y1="186" x2="310" y2="186" stroke="#FFCD00" strokeWidth="2" strokeDasharray="12 10" opacity="0.5" />
    {/* The lot and the car share one shift, so the drive-in animation stays lined up with the stalls */}
    <g transform={`translate(${LOT_SHIFT_X} 0)`}>
      <g stroke="rgba(247,248,250,0.5)" strokeWidth="2" fill="none">
        {[...STALL_X, 320].map((x) => (
          <line key={x} x1={x} y1={50} x2={x} y2={150} />
        ))}
        <line x1={40} y1={50} x2={320} y2={50} />
      </g>
      <rect className="ml-open" x={STALL_X[2] + 3} y={53} width={64} height={94} rx={6} />
      {PARKED.map((i, n) => (
        <LotCar key={i} cx={STALL_X[i] + 35} cy={100} color={PARKED_COLORS[n]} />
      ))}
      <g className="ml-car">
        <LotCar cx={0} cy={0} color="#FFCD00" />
      </g>
    </g>
  </svg>
);

/**
 * The default loading screen: covers the whole window (planner panel included),
 * a car pulls into the one open stall on a loop. Fades out when `visible` turns false.
 */
export const LoadingScreen: React.FC<{ visible?: boolean; label?: string }> = ({
  visible = true,
  label = 'Loading ParkSmart',
}) => (
  <div className={`ml ml--screen${visible ? '' : ' ml--done'}`} aria-hidden={!visible}>
    <div className="ml-inner" role="status">
      <Scene />
      <p className="ml-text">{label}</p>
    </div>
  </div>
);

/** The same scene, sized to sit inside a panel while something loads there. */
export const LoadingInline: React.FC<{ label: string }> = ({ label }) => (
  <div className="ml ml--inline">
    <div className="ml-inner" role="status">
      <Scene />
      <p className="ml-text">{label}</p>
    </div>
  </div>
);
