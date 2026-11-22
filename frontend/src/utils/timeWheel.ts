/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

/** A time as the wheel shows it: 1 to 12, 0 to 59, and AM or PM. */
export interface WheelTime {
  hour12: number;
  minute: number;
  pm: boolean;
}

/** "13:05" becomes 1:05 PM. Anything unreadable falls back to 12:00 AM, so the wheel always has a position. */
export function toWheelTime(time24: string): WheelTime {
  const m = /^(\d{1,2}):(\d{2})/.exec(time24);
  const hour = m ? Number(m[1]) : NaN;
  const minute = m ? Number(m[2]) : NaN;
  if (!m || hour > 23 || minute > 59) return { hour12: 12, minute: 0, pm: false };
  return { hour12: hour % 12 === 0 ? 12 : hour % 12, minute, pm: hour >= 12 };
}

/** 1:05 PM becomes "13:05", the format the planner and the time input use. */
export function fromWheelTime({ hour12, minute, pm }: WheelTime): string {
  const hour = (hour12 % 12) + (pm ? 12 : 0);
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
}

/** The copy of a looping list's item closest to where the wheel is now, so it rolls the short way. */
export function nearestLoopIndex(currentIndex: number, value: number, length: number): number {
  const base = Math.floor(currentIndex / length) * length + value;
  return [base - length, base, base + length].reduce((best, c) =>
    Math.abs(c - currentIndex) < Math.abs(best - currentIndex) ? c : best
  );
}
