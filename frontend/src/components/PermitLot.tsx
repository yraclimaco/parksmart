/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { CAR_COLORS, LotCar, useInView } from './LotParts';

const PERMITS = ['A', 'B', 'S', 'SR', 'D', 'V'] as const;
type Permit = (typeof PERMITS)[number];

/** A simplified example lot. Each stall belongs to one permit type. */
const STALLS: readonly Permit[] = [
  'A', 'A', 'B', 'B', 'S', 'S', 'S', 'SR', 'SR', 'D',
  'V', 'V', 'S', 'S', 'B', 'B', 'A', 'SR', 'D', 'D',
];
const OCCUPIED = new Set([0, 2, 3, 5, 7, 8, 11, 13, 14, 16, 18]);
const W = 72;
const X0 = 40;
const ROW_Y = [40, 220];
const H = 100;

export const PermitLot: React.FC = () => {
  const [permit, setPermit] = React.useState<Permit>('S');
  const [ref, seen] = useInView<HTMLDivElement>();
  const yours = STALLS.filter((p) => p === permit).length;

  return (
    <div className="pl" ref={ref}>
      <div className="pl-readout">
        <strong>{yours}</strong>
        <span>of {STALLS.length} stalls are yours</span>
      </div>
      <svg className={`pl-lot${seen ? ' pl-lot--in' : ''}`} viewBox="0 0 800 360" role="img" aria-label={`Example lot with the ${permit} permit stalls highlighted`}>
        <rect width="800" height="360" fill="#101D33" />
        <line x1="40" y1="180" x2="760" y2="180" stroke="#FFCD00" strokeWidth="3" strokeDasharray="18 14" opacity="0.7" />
        {STALLS.map((p, i) => {
          const row = Math.floor(i / 10);
          const col = i % 10;
          const x = X0 + col * W;
          const y = ROW_Y[row];
          const match = p === permit;
          const occupied = OCCUPIED.has(i);
          return (
            <g key={i} className="pl-stall" style={{ opacity: match ? 1 : 0.25 }}>
              <rect
                x={x + 3}
                y={y + 3}
                width={W - 6}
                height={H - 6}
                rx="6"
                fill={match ? 'rgba(255,205,0,0.2)' : 'transparent'}
                stroke={match ? '#FFCD00' : 'rgba(247,248,250,0.55)'}
                strokeWidth={match ? 3 : 2}
              />
              {occupied && (
                <g className="pl-car" style={{ ['--i' as string]: i, ['--from' as string]: row === 0 ? '-70px' : '70px' }}>
                  <LotCar cx={x + W / 2} cy={y + H / 2 + (row === 0 ? 8 : -8)} color={CAR_COLORS[(i * 5) % 5]} scale={1.1} />
                </g>
              )}
              <text x={x + W / 2} y={row === 0 ? y + 26 : y + H - 12} textAnchor="middle" className="pl-letter" fill={match ? '#FFCD00' : '#F7F8FA'}>
                {p}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="pl-buttons" role="group" aria-label="Choose a permit">
        {PERMITS.map((p) => (
          <button key={p} type="button" className={`pl-btn${p === permit ? ' pl-btn--on' : ''}`} aria-pressed={p === permit} onClick={() => setPermit(p)}>
            {p}
          </button>
        ))}
      </div>
    </div>
  );
};
