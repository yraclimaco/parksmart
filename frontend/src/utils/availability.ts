/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Single source of truth for how availability percentages are bucketed and colored,
 * shared by map pins, recommendation cards and the lot detail card.
 */

/** Percent of spaces open at or above which a lot counts as having plenty of space. */
export const PLENTY_THRESHOLD = 75;
/**
 * Percent of spaces open at or below which a lot counts as "nearly full". Matches the
 * backend's "Often nearly full" wording (NEAR_FULL_FRACTION = 0.10 in src/ranking.py),
 * so a card never says "Usually full" while its explanation says e.g. "about 30% open".
 */
export const NEARLY_FULL_MAX = 10;

export type AvailabilityLevel = 'plenty' | 'filling' | 'nearlyFull';

export interface AvailabilityStatus {
  level: AvailabilityLevel;
  label: string;
  /** Green / amber / red for fills, bars and dots */
  color: string;
  /** Darker shade of the same hue, readable as text on white */
  textColor: string;
}

const STATUS: Record<AvailabilityLevel, AvailabilityStatus> = {
  plenty: { level: 'plenty', label: 'Usually open', color: '#1E8E5A', textColor: '#136B42' },
  filling: { level: 'filling', label: 'Getting tight', color: '#D98A00', textColor: '#835300' },
  nearlyFull: { level: 'nearlyFull', label: 'Usually full', color: '#C0392B', textColor: '#A12116' },
};

/** Buckets an availability percentage into a level with its label and color. */
export function availabilityStatus(percent: number): AvailabilityStatus {
  if (percent >= PLENTY_THRESHOLD) return STATUS.plenty;
  if (percent <= NEARLY_FULL_MAX) return STATUS.nearlyFull;
  return STATUS.filling;
}
