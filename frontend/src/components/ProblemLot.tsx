/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { CAR_COLORS, LotCar, prefersReducedMotion, useInView } from './LotParts';

/** Stalls per row, and the size and position of the two rows (viewBox is 460 x 280). */
const COLS = 6;
const STALL_W = 56;
const STALL_H = 60;
const X0 = 62;
const ROW_Y = [36, 172] as const;
const AISLE_Y = 135;
const CAR_SCALE = 0.85;

/** What each stall shows: a parked car, or a question mark because nobody can tell if it is free. */
const STALLS: readonly ('car' | 'unknown')[][] = [
  ['car', 'unknown', 'car', 'unknown', 'unknown', 'car'],
  ['unknown', 'car', 'unknown', 'car', 'car', 'unknown'],
];

/** Seconds for one lap of the lot. */
const LAP_SECONDS = 11;

/**
 * The searching car's route: along the aisle, down the right side, back under the bottom row
 * and up the left side. It passes every stall on the way and never finds out which are free.
 */
const LOOP_PATH =
  'M 40 135 H 410 Q 440 135 440 165 V 224 Q 440 252 412 252 H 48 Q 22 252 22 224 V 165 Q 22 135 40 135 Z';

/**
 * Screen 2's picture: a lot where most of what you would want to know is hidden. Cars sit in
 * some stalls, the rest show a "?", and a yellow car circles looking for a space. Illustration
 * only: it shows no real counts. With reduced motion the car stays put and nothing pulses.
 */
export const ProblemLot: React.FC = () => {
  const [ref, seen] = useInView<HTMLDivElement>();
  const still = prefersReducedMotion();

  return (
    <div className="pr" ref={ref}>
      <svg
        className="pr-lot"
        viewBox="0 0 460 280"
        role="img"
        aria-label="A parking lot where some stalls hold cars and the rest show a question mark, because nothing says which are open. A yellow car circles the lot looking for a space."
      >
        <rect width="460" height="280" rx="18" fill="#101D33" />
        <line x1="14" y1={AISLE_Y} x2="446" y2={AISLE_Y} stroke="#FFCD00" strokeWidth="2" strokeDasharray="12 10" opacity="0.4" />

        <g stroke="rgba(247,248,250,0.45)" strokeWidth="2" fill="none">
          {ROW_Y.map((y) => (
            <React.Fragment key={y}>
              {Array.from({ length: COLS + 1 }, (_, c) => (
                <line key={c} x1={X0 + c * STALL_W} y1={y} x2={X0 + c * STALL_W} y2={y + STALL_H} />
              ))}
              <line x1={X0} y1={y} x2={X0 + COLS * STALL_W} y2={y} />
              <line x1={X0} y1={y + STALL_H} x2={X0 + COLS * STALL_W} y2={y + STALL_H} />
            </React.Fragment>
          ))}
        </g>

        {STALLS.map((row, r) =>
          row.map((kind, c) => {
            const cx = X0 + c * STALL_W + STALL_W / 2;
            const cy = ROW_Y[r] + STALL_H / 2;
            const index = r * COLS + c;
            return kind === 'car' ? (
              <LotCar key={`${r}-${c}`} cx={cx} cy={cy} color={CAR_COLORS[(index * 5) % 5]} scale={CAR_SCALE} />
            ) : (
              <text
                key={`${r}-${c}`}
                className="pr-q"
                x={cx}
                y={cy + 11}
                textAnchor="middle"
                style={{ animationDelay: `${(index * 0.37) % 2.4}s` }}
              >
                ?
              </text>
            );
          })
        )}

        {/* The searching car: nose along the direction of travel */}
        <g transform={still ? `translate(${X0 + 40} ${AISLE_Y})` : undefined}>
          {!still && seen && (
            <animateMotion dur={`${LAP_SECONDS}s`} repeatCount="indefinite" rotate="auto" path={LOOP_PATH} />
          )}
          <g transform="rotate(90)">
            <LotCar cx={0} cy={0} color="#FFCD00" scale={CAR_SCALE} />
          </g>
        </g>
      </svg>
    </div>
  );
};
