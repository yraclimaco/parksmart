/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { fromWheelTime, nearestLoopIndex, toWheelTime } from '../utils/timeWheel.ts';

/** Height of one row, and how many rows show (the middle one is the selection). */
const ITEM_HEIGHT = 36;
const VISIBLE_ROWS = 3;
/** Looping wheels repeat their list this many times so they can always be rolled either way. */
const LOOP_COPIES = 5;
/** Quiet time after the last scroll movement before the wheel counts as settled. */
const SETTLE_MS = 110;

const HOURS = Array.from({ length: 12 }, (_, i) => String(i + 1));
const MINUTES = Array.from({ length: 60 }, (_, i) => String(i).padStart(2, '0'));
const PERIODS = ['AM', 'PM'];

const mod = (n: number, m: number) => ((n % m) + m) % m;

interface WheelColumnProps {
  label: string;
  items: string[];
  selected: number;
  /** Rolls past the end back to the start (hours and minutes, like the iPhone clock). */
  loop: boolean;
  /** Tailwind width class for the column. */
  width: string;
  onSelect: (index: number) => void;
}

/** One rolling column: scroll or swipe to spin it, arrow keys step it, click a row to pick it. */
const WheelColumn: React.FC<WheelColumnProps> = ({ label, items, selected, loop, width, onSelect }) => {
  const ref = useRef<HTMLDivElement | null>(null);
  const n = items.length;
  const copies = loop ? LOOP_COPIES : 1;
  const middleCopy = Math.floor(copies / 2);
  const [live, setLive] = useState(loop ? middleCopy * n + selected : selected);
  const settleTimer = useRef<number | null>(null);
  const frame = useRef<number | null>(null);
  const mounted = useRef(false);
  // The timer callback must see the latest values, not the ones from when it was set. The ref is
  // updated in an effect, not during render, so rendering stays free of side effects.
  const latest = useRef({ selected, onSelect });
  useLayoutEffect(() => {
    latest.current = { selected, onSelect };
  });

  const rawIndex = () => Math.round((ref.current?.scrollTop ?? 0) / ITEM_HEIGHT);

  // Put the wheel on the selected value: at once the first time, then rolling when it is
  // changed from outside (a class tapped, arrow keys, "Use now"). A wheel the person just
  // spun already shows its value, so nothing moves.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const first = !mounted.current;
    mounted.current = true;
    const current = rawIndex();
    if (!first && mod(current, n) === selected) return;
    const target = loop ? (first ? middleCopy * n + selected : nearestLoopIndex(current, selected, n)) : selected;
    el.scrollTo({ top: target * ITEM_HEIGHT, behavior: first ? 'auto' : 'smooth' });
    setLive(target);
  }, [selected, n, loop, middleCopy]);

  useEffect(
    () => () => {
      if (settleTimer.current !== null) window.clearTimeout(settleTimer.current);
      if (frame.current !== null) window.cancelAnimationFrame(frame.current);
    },
    []
  );

  const handleScroll = () => {
    if (frame.current === null) {
      frame.current = window.requestAnimationFrame(() => {
        frame.current = null;
        setLive(rawIndex());
      });
    }
    if (settleTimer.current !== null) window.clearTimeout(settleTimer.current);
    settleTimer.current = window.setTimeout(() => {
      const el = ref.current;
      if (!el) return;
      const index = rawIndex();
      const value = mod(index, n);
      if (value !== latest.current.selected) latest.current.onSelect(value);
      // Slip back to the middle copy without anyone noticing, so there is always room to roll
      if (loop && Math.floor(index / n) !== middleCopy) {
        el.scrollTo({ top: (middleCopy * n + value) * ITEM_HEIGHT, behavior: 'auto' });
        setLive(middleCopy * n + value);
      }
    }, SETTLE_MS);
  };

  const step = (delta: number) => {
    const next = loop ? mod(selected + delta, n) : Math.min(n - 1, Math.max(0, selected + delta));
    if (next !== selected) onSelect(next);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    const keys: Record<string, number> = { ArrowUp: -1, ArrowDown: 1, PageUp: -5, PageDown: 5 };
    if (e.key in keys) {
      e.preventDefault();
      step(keys[e.key]);
    } else if (!loop && e.key === 'Home') {
      e.preventDefault();
      onSelect(0);
    } else if (!loop && e.key === 'End') {
      e.preventDefault();
      onSelect(n - 1);
    }
  };

  return (
    <div
      ref={ref}
      role="spinbutton"
      tabIndex={0}
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={n - 1}
      aria-valuenow={selected}
      aria-valuetext={items[selected]}
      onScroll={handleScroll}
      onKeyDown={handleKeyDown}
      className={`tw-col relative z-10 ${width} overflow-y-scroll overscroll-contain rounded-md focus:outline-none focus-visible:ring-2 focus-visible:ring-sky`}
      style={{
        height: ITEM_HEIGHT * VISIBLE_ROWS,
        scrollSnapType: 'y mandatory',
        touchAction: 'pan-y',
        // Rows fade out toward the top and bottom edges
        maskImage: 'linear-gradient(to bottom, transparent, #000 32%, #000 68%, transparent)',
        WebkitMaskImage: 'linear-gradient(to bottom, transparent, #000 32%, #000 68%, transparent)',
      }}
    >
      <div style={{ paddingTop: ITEM_HEIGHT, paddingBottom: ITEM_HEIGHT }}>
        {Array.from({ length: copies * n }, (_, g) => {
          const distance = Math.abs(g - live);
          return (
            <div
              key={g}
              aria-hidden="true"
              onClick={() => onSelect(g % n)}
              className="flex items-center justify-center tabular-nums cursor-pointer select-none"
              style={{
                height: ITEM_HEIGHT,
                scrollSnapAlign: 'center',
                opacity: distance === 0 ? 1 : distance === 1 ? 0.5 : 0.22,
                transform: `scale(${distance === 0 ? 1 : 0.88})`,
                fontSize: distance === 0 ? 22 : 18,
                fontWeight: distance === 0 ? 600 : 500,
                color: '#182B49',
                transition: 'opacity 120ms ease, transform 120ms ease',
              }}
            >
              {items[g % n]}
            </div>
          );
        })}
      </div>
    </div>
  );
};

interface TimeWheelProps {
  /** "HH:MM", 24-hour. */
  value: string;
  onChange: (value: string) => void;
  invalid?: boolean;
  describedBy?: string;
}

/**
 * Time picker that rolls like the iPhone clock: spin the hour, minute and AM/PM columns
 * instead of typing. Hours and minutes loop; changing the hour never flips AM/PM.
 */
export const TimeWheel: React.FC<TimeWheelProps> = ({ value, onChange, invalid = false, describedBy }) => {
  const t = toWheelTime(value);
  return (
    <div
      id="arrival-time"
      role="group"
      aria-label="Arrival time"
      aria-invalid={invalid}
      aria-describedby={describedBy}
      className={`relative flex items-center justify-center gap-1 rounded-[10px] bg-white border ${
        invalid ? 'border-[#C0392B]' : 'border-line'
      }`}
      style={{ height: ITEM_HEIGHT * VISIBLE_ROWS }}
    >
      {/* The selection band behind the middle row */}
      <div
        aria-hidden="true"
        className="absolute inset-x-2 rounded-lg bg-paper border-y border-line pointer-events-none"
        style={{ top: ITEM_HEIGHT, height: ITEM_HEIGHT }}
      />
      <WheelColumn
        label="Hour"
        items={HOURS}
        selected={t.hour12 - 1}
        loop
        width="w-14"
        onSelect={(i) => onChange(fromWheelTime({ ...t, hour12: i + 1 }))}
      />
      <span aria-hidden="true" className="relative z-10 text-[22px] font-semibold text-navy pb-0.5">
        :
      </span>
      <WheelColumn
        label="Minute"
        items={MINUTES}
        selected={t.minute}
        loop
        width="w-14"
        onSelect={(i) => onChange(fromWheelTime({ ...t, minute: i }))}
      />
      <WheelColumn
        label="AM or PM"
        items={PERIODS}
        selected={t.pm ? 1 : 0}
        loop={false}
        width="w-16"
        onSelect={(i) => onChange(fromWheelTime({ ...t, pm: i === 1 }))}
      />
    </div>
  );
};
