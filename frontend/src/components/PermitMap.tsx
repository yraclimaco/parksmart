/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { useInView } from './LotParts';

const PERMITS = ['A', 'B', 'S', 'SR', 'D', 'V'] as const;
type Permit = (typeof PERMITS)[number];
type Stall = 'A' | 'B' | 'S' | 'SR' | 'D' | 'Visitor';
/** y: allowed, c: needs checking (ParkSmart never recommends it), n: not allowed. */
type Access = 'y' | 'c' | 'n';

const TIMES = [
  { id: 'weekday10', label: 'Weekday 10 AM' },
  { id: 'weekday18', label: 'Weekday 6 PM' },
  { id: 'sat12', label: 'Saturday noon' },
] as const;
type TimeId = (typeof TIMES)[number]['id'];

/**
 * Which stall types each permit may use at each example time. Generated from the backend's real
 * rules, `check_eligibility` in src/eligibility.py (yraclimaco/parksmart), for Wed Nov 18, 2026 at
 * 10:00 and 18:00 and Sat Nov 21, 2026 at 12:00. Regenerate when the permit rules change.
 * Columns: A, B, S, SR, D, Visitor.
 */
const ACCESS: Record<TimeId, Record<Permit, string>> = {
  weekday10: { A: 'yyyncn', B: 'nyyncn', S: 'nnyncn', SR: 'nnyycn', D: 'nnnnyn', V: 'nnnncy' },
  weekday18: { A: 'yyyncn', B: 'yyyncn', S: 'yyyncn', SR: 'yyyycn', D: 'yyynyn', V: 'yyyncy' },
  sat12: { A: 'yyyncn', B: 'yyyncn', S: 'yyyncn', SR: 'yyyycn', D: 'yyynyn', V: 'nyyncy' },
};
const STALL_ORDER: readonly Stall[] = ['A', 'B', 'S', 'SR', 'D', 'Visitor'];

export function permitAccess(time: TimeId, permit: Permit, stall: Stall): Access {
  return ACCESS[time][permit][STALL_ORDER.indexOf(stall)] as Access;
}

/** Made-up lots around a made-up campus. Only the rules are real. */
const LOTS: readonly { stall: Stall; x: number; y: number }[] = [
  { stall: 'A', x: 70, y: 40 },
  { stall: 'B', x: 325, y: 24 },
  { stall: 'S', x: 580, y: 40 },
  { stall: 'SR', x: 610, y: 196 },
  { stall: 'D', x: 580, y: 352 },
  { stall: 'Visitor', x: 325, y: 368 },
  { stall: 'S', x: 70, y: 352 },
  { stall: 'B', x: 40, y: 196 },
];
const LOT_W = 150;
const LOT_H = 76;

const stallName = (s: Stall) => (s === 'Visitor' ? 'Visitor' : s);

/**
 * Screen 4's picture: an example campus map. Pick a permit and an arrival time, and lots that
 * permit cannot use at that time fade out, following the backend's real permit rules. D stalls
 * for other permits show as "check signs", because ParkSmart treats them as unconfirmed and never
 * recommends them.
 */
export const PermitMap: React.FC = () => {
  const [permit, setPermit] = React.useState<Permit>('S');
  const [time, setTime] = React.useState<TimeId>('weekday10');
  const [ref, seen] = useInView<HTMLDivElement>();

  const usable = STALL_ORDER.filter((s) => permitAccess(time, permit, s) === 'y').map(stallName);
  const check = STALL_ORDER.filter((s) => permitAccess(time, permit, s) === 'c').map(stallName);
  const timeLabel = TIMES.find((t) => t.id === time)?.label ?? '';

  return (
    <div className="pm" ref={ref}>
      <div className="pm-controls">
        <div className="pm-row" role="group" aria-label="Your permit">
          <span className="pm-label">Permit</span>
          {PERMITS.map((p) => (
            <button key={p} type="button" className={`pm-btn${p === permit ? ' pm-btn--on' : ''}`} aria-pressed={p === permit} onClick={() => setPermit(p)}>
              {p}
            </button>
          ))}
        </div>
        <div className="pm-row" role="group" aria-label="Arrival time">
          <span className="pm-label">Arriving</span>
          {TIMES.map((t) => (
            <button key={t.id} type="button" className={`pm-time${t.id === time ? ' pm-time--on' : ''}`} aria-pressed={t.id === time} onClick={() => setTime(t.id)}>
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <svg className={`pm-map${seen ? ' pm-map--in' : ''}`} viewBox="0 0 800 460" role="img" aria-label={`Example campus map. With a ${permit} permit on ${timeLabel}, you can use ${usable.join(', ')} lots.`}>
        <defs>
          <pattern id="pm-hatch" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="10" height="10" fill="#101D33" />
            <line x1="0" y1="0" x2="0" y2="10" stroke="rgba(247,248,250,0.35)" strokeWidth="4" />
          </pattern>
        </defs>
        <rect width="800" height="460" rx="18" fill="#101D33" />
        <rect x="235" y="128" width="330" height="204" rx="60" fill="none" stroke="rgba(247,248,250,0.14)" strokeWidth="22" />
        <g aria-hidden="true">
          <rect x="300" y="178" width="70" height="44" rx="6" fill="#24406B" />
          <rect x="384" y="168" width="54" height="64" rx="6" fill="#24406B" />
          <rect x="452" y="184" width="50" height="40" rx="6" fill="#24406B" />
          <rect x="330" y="236" width="140" height="40" rx="6" fill="#24406B" />
          <text x="400" y="304" textAnchor="middle" className="pm-campus">Campus</text>
        </g>
        {LOTS.map((lot, i) => {
          const access = permitAccess(time, permit, lot.stall);
          return (
            <g key={i} className={`pm-lot pm-lot--${access}`} style={{ '--pm-i': i } as React.CSSProperties}>
              <rect
                x={lot.x}
                y={lot.y}
                width={LOT_W}
                height={LOT_H}
                rx="10"
                fill={access === 'y' ? '#FFCD00' : access === 'c' ? 'url(#pm-hatch)' : '#1B2A44'}
                stroke={access === 'y' ? '#FFCD00' : 'rgba(247,248,250,0.35)'}
                strokeWidth="2"
                strokeDasharray={access === 'c' ? '6 5' : undefined}
              />
              <text x={lot.x + LOT_W / 2} y={lot.y + LOT_H / 2 + 2} textAnchor="middle" dominantBaseline="middle" className="pm-letter">
                {lot.stall === 'Visitor' ? 'Visitor' : `${lot.stall} lot`}
              </text>
              {access === 'c' && (
                <text x={lot.x + LOT_W / 2} y={lot.y + LOT_H - 10} textAnchor="middle" className="pm-check">
                  check signs
                </text>
              )}
            </g>
          );
        })}
      </svg>

      <p className="pm-readout" aria-live="polite">
        <strong>
          {permit} permit, {timeLabel.toLowerCase()}:
        </strong>{' '}
        {usable.join(', ')} lots.
        {check.length > 0 && ` ${check.join(', ')} stalls: ParkSmart leaves them out until UCSD's rules are confirmed.`}
      </p>
    </div>
  );
};
