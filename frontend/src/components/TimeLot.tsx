/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { CAR_COLORS, LotCar, prefersReducedMotion, useInView } from './LotParts';

const COLS = 14;
const ROWS_Y = [30, 170];
const SW = 52;
const SH = 80;
const X0 = 36;
const TOTAL = COLS * ROWS_Y.length;

/** Illustrative demand curve: how full a busy lot typically gets over a weekday. */
const CURVE: readonly (readonly [number, number])[] = [
  [7, 0.2], [8, 0.45], [9, 0.75], [10, 0.9], [11, 0.96], [12, 0.97],
  [13, 0.93], [14, 0.85], [15, 0.75], [16, 0.6], [17, 0.4], [18, 0.25],
];

const occupancy = (h: number): number => {
  for (let i = 1; i < CURVE.length; i += 1) {
    const [h1, v1] = CURVE[i];
    const [h0, v0] = CURVE[i - 1];
    if (h <= h1) return v0 + ((h - h0) / (h1 - h0)) * (v1 - v0);
  }
  return CURVE[CURVE.length - 1][1];
};

/** A fixed shuffle so cars always arrive in the same order. */
const RANK: number[] = (() => {
  const idx = Array.from({ length: TOTAL }, (_, i) => i);
  let s = 11;
  for (let i = idx.length - 1; i > 0; i -= 1) {
    s = (s * 1103515245 + 12345) % 2147483648;
    const j = s % (i + 1);
    [idx[i], idx[j]] = [idx[j], idx[i]];
  }
  const rank = new Array<number>(TOTAL);
  idx.forEach((stall, pos) => {
    rank[stall] = pos / TOTAL;
  });
  return rank;
})();

const formatHour = (h: number): string => {
  const hh = Math.floor(h);
  const mm = Math.round((h - hh) * 60);
  const suffix = hh >= 12 ? 'PM' : 'AM';
  const h12 = hh % 12 === 0 ? 12 : hh % 12;
  return `${h12}:${mm.toString().padStart(2, '0')} ${suffix}`;
};

export const TimeLot: React.FC = () => {
  const [hour, setHour] = React.useState(7);
  const touched = React.useRef(false);
  const [dragged, setDragged] = React.useState(false);
  const [ref, seen] = useInView<HTMLDivElement>();

  React.useEffect(() => {
    if (!seen) return;
    if (prefersReducedMotion()) {
      setHour(12);
      return;
    }
    let raf = 0;
    const start = performance.now();
    const frame = (now: number) => {
      if (touched.current) return;
      const p = Math.min(1, (now - start) / 5000);
      setHour(7 + (1 - Math.pow(1 - p, 2)) * 5);
      if (p < 1) raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, [seen]);

  const occ = occupancy(hour);
  const taken = RANK.map((r) => r < occ);
  const free = taken.filter((x) => !x).length;
  const openPct = Math.round((free / TOTAL) * 100);
  const state = openPct >= 40 ? 'open' : openPct >= 12 ? 'filling' : 'full';
  const label = state === 'open' ? 'Usually open' : state === 'filling' ? 'Filling up' : 'Usually full';

  return (
    <div className="tl" ref={ref}>
      <div className="tl-controls">
      <div className="tl-top">
        <div className="tl-time">{formatHour(hour)}</div>
        <div className={`tl-state tl-state--${state}`}>
          <strong>{openPct}%</strong>
          <span>{label}</span>
        </div>
      </div>
      <p className={`tl-cue${dragged ? ' tl-cue--gone' : ''}`} aria-hidden={dragged}>
        <span aria-hidden="true">&larr;</span> Drag the slider to change the time <span aria-hidden="true">&rarr;</span>
      </p>
      <input
        className="tl-range"
        type="range"
        min={7}
        max={18}
        step={0.25}
        value={hour}
        aria-label="Time of day"
        onChange={(e) => {
          touched.current = true;
          setDragged(true);
          setHour(Number(e.target.value));
        }}
      />
      <div className="tl-ticks" aria-hidden="true">
        <span>7 AM</span>
        <span>12 PM</span>
        <span>6 PM</span>
      </div>
      </div>
      <svg className="tl-lot" viewBox="0 0 800 280" role="img" aria-label={`Example lot at ${formatHour(hour)}, ${openPct} percent open`}>
        <rect width="800" height="280" fill="#101D33" />
        <line x1="36" y1="140" x2="764" y2="140" stroke="#FFCD00" strokeWidth="3" strokeDasharray="18 14" opacity="0.6" />
        <g stroke="rgba(247,248,250,0.45)" strokeWidth="2">
          {ROWS_Y.map((y) => (
            <React.Fragment key={y}>
              {Array.from({ length: COLS + 1 }, (_, c) => (
                <line key={c} x1={X0 + c * SW} y1={y} x2={X0 + c * SW} y2={y + SH} />
              ))}
            </React.Fragment>
          ))}
          <line x1={X0} y1={30} x2={X0 + COLS * SW} y2={30} />
          <line x1={X0} y1={110} x2={X0 + COLS * SW} y2={110} />
          <line x1={X0} y1={170} x2={X0 + COLS * SW} y2={170} />
          <line x1={X0} y1={250} x2={X0 + COLS * SW} y2={250} />
        </g>
        {taken.map((isTaken, i) => {
          const row = Math.floor(i / COLS);
          const col = i % COLS;
          const cx = X0 + col * SW + SW / 2;
          const cy = ROWS_Y[row] + SH / 2;
          return (
            <g
              key={i}
              className="tl-car"
              style={{ opacity: isTaken ? 1 : 0, transform: isTaken ? 'scale(1)' : 'scale(0.55)' }}
            >
              <LotCar cx={cx} cy={cy} color={CAR_COLORS[(i * 7) % 6]} scale={0.92} />
            </g>
          );
        })}
      </svg>
    </div>
  );
};
