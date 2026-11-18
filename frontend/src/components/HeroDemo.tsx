/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { CAR_COLORS, LotCar, prefersReducedMotion } from './LotParts';

/** A looping, hands-off demo of the planner: type a trip, get a pick, see the walk. */
const LOOP = 11.8;
const DEST = 'Geisel Library';
const PERMITS = ['A', 'B', 'S', 'SR', 'D', 'V'] as const;

const SW = 62;
const X0 = 12;
const TOP_Y = 110;
const BOT_Y = 226;
const SH = 64;
const TOP_OCC = [0, 1, 2, 4, 5, 7];
const BOT_OCC = [0, 2, 3, 5, 6, 7];
const FIRST = 3;
const BACKUP = 6;

const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const ease = (x: number) => 1 - Math.pow(1 - x, 3);

/** Walking route: up from the stall, across the plaza, up to the door. */
const ROUTE_LEN = 24 + 33 + 28;
const routePoint = (p: number) => {
  const d = p * ROUTE_LEN;
  const sx = X0 + FIRST * SW + SW / 2;
  if (d <= 24) return { x: sx, y: TOP_Y - d };
  if (d <= 57) return { x: sx + (d - 24) * (33 / 33) * ((262 - sx) / 33), y: TOP_Y - 24 };
  return { x: 262, y: TOP_Y - 24 - (d - 57) };
};

export const HeroDemo: React.FC = () => {
  const reduced = React.useMemo(prefersReducedMotion, []);
  const [t, setT] = React.useState(reduced ? 9 : 0);

  React.useEffect(() => {
    if (reduced) return;
    let raf = 0;
    let last = -1;
    const start = performance.now();
    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      const s = Math.max(0, ((now - start) / 1000) % LOOP);
      const q = Math.round(s * 30);
      if (q !== last) {
        last = q;
        setT(s);
      }
    };
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, [reduced]);

  const typed = clamp(Math.floor((t - 0.5) / 0.13), 0, DEST.length);
  const permitOn = t > 2.9;
  const pressed = t > 4.0 && t < 4.35;
  const cardP = ease(clamp((t - 4.7) / 0.5));
  const pct = Math.round(79 * ease(clamp((t - 4.9) / 1.4)));
  const firstP = ease(clamp((t - 4.7) / 0.4));
  const backupP = ease(clamp((t - 5.2) / 0.4));
  const routeP = ease(clamp((t - 5.4) / 1.3));
  const pinP = ease(clamp((t - 6.5) / 0.4));
  const fade = reduced ? 1 : clamp(Math.min(t / 0.35, (LOOP - t) / 0.7));
  const walker = routePoint(routeP);

  const stallX = (i: number) => X0 + i * SW;
  const lines: React.ReactNode[] = [];
  for (let i = 0; i <= 8; i += 1) {
    lines.push(
      <line key={`t${i}`} x1={stallX(i)} y1={TOP_Y} x2={stallX(i)} y2={TOP_Y + SH} />,
      <line key={`b${i}`} x1={stallX(i)} y1={BOT_Y} x2={stallX(i)} y2={BOT_Y + SH} />,
    );
  }

  return (
    <div className="hd-window" style={{ opacity: fade }} aria-hidden="true">
      <div className="hd-form">
        <div className="hd-field-label">Destination</div>
        <div className="hd-field">
          <span>{DEST.slice(0, typed)}</span>
          {typed < DEST.length && <i className="hd-caret" />}
        </div>
        <div className="hd-field-label">Permit</div>
        <div className="hd-permits">
          {PERMITS.map((p) => (
            <span key={p} className={`hd-permit${permitOn && p === 'S' ? ' hd-permit--on' : ''}`}>
              {p}
            </span>
          ))}
        </div>
        <div className={`hd-go${pressed ? ' hd-go--pressed' : ''}`}>Find parking</div>
        <div className="hd-card" style={{ opacity: cardP, transform: `translateY(${(1 - cardP) * 18}px)` }}>
          <span className="hd-pill">First choice</span>
          <div className="hd-lot">Lot P503</div>
          <div className="hd-walk">
            <b>5 min</b> walk
          </div>
          <div className="hd-open">
            <b>{pct}%</b> usually open
          </div>
          <div className="hd-bar">
            <i style={{ width: `${pct}%` }} />
          </div>
        </div>
      </div>

      <svg className="hd-scene" viewBox="0 0 520 300" role="presentation">
        <rect width="520" height="300" fill="#101D33" />
        <rect x="150" y="8" width="220" height="48" rx="6" fill="#24406B" />
        <text x="260" y="38" textAnchor="middle" className="hd-bldg">
          Geisel Library
        </text>
        <g stroke="rgba(247,248,250,0.5)" strokeWidth="2" fill="none">
          {lines}
          <line x1={X0} y1={TOP_Y} x2={X0 + 8 * SW} y2={TOP_Y} />
          <line x1={X0} y1={BOT_Y + SH} x2={X0 + 8 * SW} y2={BOT_Y + SH} />
        </g>
        <line x1="12" y1="200" x2="508" y2="200" stroke="#FFCD00" strokeWidth="2" strokeDasharray="14 12" opacity="0.7" />
        {TOP_OCC.map((i) => (
          <LotCar key={`ct${i}`} cx={stallX(i) + SW / 2} cy={TOP_Y + SH / 2} color={CAR_COLORS[(i * 2) % 5]} />
        ))}
        {BOT_OCC.map((i) => (
          <LotCar key={`cb${i}`} cx={stallX(i) + SW / 2} cy={BOT_Y + SH / 2} color={CAR_COLORS[(i * 3 + 1) % 5]} />
        ))}
        <g opacity={firstP}>
          <rect
            x={stallX(FIRST) + 3}
            y={TOP_Y + 3}
            width={SW - 6}
            height={SH - 6}
            rx="6"
            fill="rgba(255,205,0,0.22)"
            stroke="#FFCD00"
            strokeWidth="3"
          />
          <circle cx={stallX(FIRST) + SW / 2} cy={TOP_Y + SH / 2} r="15" fill="#FFCD00" />
          <text x={stallX(FIRST) + SW / 2} y={TOP_Y + SH / 2 + 7} textAnchor="middle" className="hd-num">
            1
          </text>
        </g>
        <g opacity={backupP}>
          <rect
            x={stallX(BACKUP) + 3}
            y={TOP_Y + 3}
            width={SW - 6}
            height={SH - 6}
            rx="6"
            fill="rgba(247,248,250,0.1)"
            stroke="#F7F8FA"
            strokeWidth="2.5"
            strokeDasharray="6 5"
          />
          <circle cx={stallX(BACKUP) + SW / 2} cy={TOP_Y + SH / 2} r="15" fill="#F7F8FA" />
          <text x={stallX(BACKUP) + SW / 2} y={TOP_Y + SH / 2 + 7} textAnchor="middle" className="hd-num">
            2
          </text>
        </g>
        <path
          d={`M${X0 + FIRST * SW + SW / 2} ${TOP_Y} V${TOP_Y - 24} H262 V${TOP_Y - 24 - 28}`}
          fill="none"
          stroke="#FFCD00"
          strokeWidth="4"
          strokeLinecap="round"
          strokeLinejoin="round"
          pathLength={1}
          strokeDasharray="1"
          strokeDashoffset={1 - routeP}
          opacity={routeP > 0 ? 1 : 0}
        />
        {routeP > 0 && routeP < 1 && <circle cx={walker.x} cy={walker.y} r="6" fill="#FFFFFF" stroke="#FFCD00" strokeWidth="3" />}
        <g opacity={pinP} transform={`translate(262 ${58 - (1 - pinP) * 10})`}>
          <circle r="9" fill="#FFCD00" stroke="#101D33" strokeWidth="3" />
        </g>
      </svg>
    </div>
  );
};
