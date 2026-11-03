/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { ParkingLot } from '../types.ts';
import { PLENTY_THRESHOLD } from './availability.ts';

/**
 * SAMPLE time-of-day availability, so the UI can show how campus fills and empties
 * through a day. Shape only: weekday mornings fill toward a late-morning peak, ease
 * at lunch, empty out by evening; weekends stay mostly open. Each lot's peak depth
 * comes from its sample `estimatedAvailabilityPercent`.
 *
 * Replace `availabilityAt` with the real forecast (QPASS baseline / ML model) when the
 * backend is connected; every screen reads availability through this one function.
 */

/** Hours (decimal) and widths of the weekday demand bumps. */
const MORNING_PEAK_HOUR = 10.5;
const MORNING_PEAK_WIDTH = 2.2;
const AFTERNOON_PEAK_HOUR = 13.5;
const AFTERNOON_PEAK_WIDTH = 2.0;
const AFTERNOON_PEAK_SCALE = 0.75;
/** Weekend demand relative to a weekday. */
const WEEKEND_SCALE = 0.35;

function gaussian(x: number, center: number, width: number): number {
  return Math.exp(-((x - center) ** 2) / (2 * width ** 2));
}

/** 0 (empty campus) to 1 (peak demand) for a moment in time. */
function demandShape(date: Date): number {
  const hour = date.getHours() + date.getMinutes() / 60;
  const weekday = Math.max(
    gaussian(hour, MORNING_PEAK_HOUR, MORNING_PEAK_WIDTH),
    AFTERNOON_PEAK_SCALE * gaussian(hour, AFTERNOON_PEAK_HOUR, AFTERNOON_PEAK_WIDTH)
  );
  const day = date.getDay();
  return day === 0 || day === 6 ? weekday * WEEKEND_SCALE : weekday;
}

/** How full a lot gets at peak (0-1), derived from its sample base availability. */
function peakFullness(lot: ParkingLot): number {
  // Tuned so the late-morning peak spans the range: quiet lots stay green, busy ones go red
  return Math.min(0.9, Math.max(0.2, 1.05 - lot.estimatedAvailabilityPercent / 100));
}

/** Estimated percent of spaces open at `date` (0-100, whole number). SAMPLE. */
export function availabilityAt(lot: ParkingLot, date: Date): number {
  return Math.round(100 * (1 - peakFullness(lot) * demandShape(date)));
}

/** Search window and step for "usually tight from" insights. */
const INSIGHT_START_HOUR = 6;
const INSIGHT_END_HOUR = 20;
const INSIGHT_STEP_MINUTES = 15;

/**
 * First time on `date`'s day when the lot stops being "likely open", e.g. 9:45 AM.
 * Null if it stays likely open all day.
 */
export function tightFrom(lot: ParkingLot, date: Date): Date | null {
  const t = new Date(date);
  t.setHours(INSIGHT_START_HOUR, 0, 0, 0);
  const end = new Date(date);
  end.setHours(INSIGHT_END_HOUR, 0, 0, 0);
  for (; t <= end; t.setMinutes(t.getMinutes() + INSIGHT_STEP_MINUTES)) {
    if (availabilityAt(lot, t) < PLENTY_THRESHOLD) return new Date(t);
  }
  return null;
}
