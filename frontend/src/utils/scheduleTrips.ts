/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { CAMPUS_DESTINATIONS } from '../data/destinations.ts';
import type { CampusDestination } from '../types.ts';
import { ARRIVE_BEFORE_CLASS_MINUTES, formatClock } from './classTime.ts';

// Still exported from here, where the planner and its tests already import them
export { ARRIVE_BEFORE_CLASS_MINUTES, formatClock };

/** A name or alias shorter than this (letters only) is too generic to identify a building. */
const MIN_NAME_LENGTH = 5;
/** How many leading words of a location are tried as a schedule code ("PCYNH 106", "AP&M B402"). */
const CODE_WORDS = 2;

const clean = (text: string) => text.toLowerCase().replace(/[&.\-/,()']/g, ' ').replace(/\s+/g, ' ').trim();
/** Same, with spaces removed, so "AP&M" and "APM" compare equal. */
const compact = (text: string) => clean(text).replace(/ /g, '');

/**
 * Entries for the same name closer together than this are treated as one place. The data lists
 * a few buildings twice under different names (the Faculty Club is 43 m from the Ida and Cecil
 * Green Faculty Club). Our choice, a building footprint plus some gap, not a UCSD figure.
 */
const SAME_PLACE_METERS = 150;
const EARTH_RADIUS_METERS = 6_371_000;

/** Straight-line distance between two points, in meters (haversine). */
export function metersBetween(
  a: { latitude: number; longitude: number },
  b: { latitude: number; longitude: number }
): number {
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const dLat = toRad(b.latitude - a.latitude);
  const dLon = toRad(b.longitude - a.longitude);
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a.latitude)) * Math.cos(toRad(b.latitude)) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_RADIUS_METERS * Math.asin(Math.sqrt(h));
}

/**
 * The one destination in the list (the first, when the rest are the same place), or null when
 * there are none or several that are far apart. Never a guess between different buildings.
 */
function onlyOne(found: CampusDestination[]): CampusDestination | null {
  const distinct = [...new Map(found.map((d) => [d.id, d])).values()];
  if (distinct.length === 0) return null;
  return distinct.every((d) => metersBetween(distinct[0], d) <= SAME_PLACE_METERS) ? distinct[0] : null;
}

/**
 * A one-word alias that is also a word in this many building names is too common to pick out one
 * building. (It is also generic when it is just the last word of its own building's name.)
 */
const GENERIC_ALIAS_MIN_BUILDINGS = 3;

/** For each word, how many buildings have it in their name. */
const BUILDINGS_PER_NAME_WORD = new Map<string, number>();
for (const { name } of CAMPUS_DESTINATIONS) {
  for (const word of new Set(clean(name).split(' '))) {
    BUILDINGS_PER_NAME_WORD.set(word, (BUILDINGS_PER_NAME_WORD.get(word) ?? 0) + 1);
  }
}

/**
 * True for an alias like "Auditorium": one word that is common across building names, or the
 * closing word of its own building's name. The data gives a far-off forum that alias, and it
 * would otherwise claim every "<Anything> Auditorium" on campus.
 */
function isGenericAlias(alias: string, destination: CampusDestination): boolean {
  const word = clean(alias);
  if (word.includes(' ')) return false;
  return (
    (BUILDINGS_PER_NAME_WORD.get(word) ?? 0) >= GENERIC_ALIAS_MIN_BUILDINGS ||
    clean(destination.name).endsWith(` ${word}`)
  );
}

interface Label {
  label: string;
  destination: CampusDestination;
  /** A building's own name beats another building's alias of the same length. */
  isName: boolean;
}

/** Every name and usable alias, so a longer label ("Marine Biology Building") beats a shorter one inside it. */
const LABELS: Label[] = CAMPUS_DESTINATIONS.flatMap((destination) => [
  { label: destination.name, destination, isName: true },
  ...(destination.aliases ?? [])
    .filter((alias) => !isGenericAlias(alias, destination))
    .map((alias) => ({ label: alias, destination, isName: false })),
]);

/**
 * The building named in `text`: the longest name or alias written out as whole words, a name
 * beating an alias of the same length, and null when buildings still tie (never a guess).
 */
function buildingWrittenOut(text: string): CampusDestination | null {
  const hits = LABELS.filter(({ label }) => {
    const c = clean(label);
    return c.replace(/ /g, '').length >= MIN_NAME_LENGTH && text.includes(` ${c} `);
  });
  if (hits.length === 0) return null;
  const longest = Math.max(...hits.map(({ label }) => clean(label).length));
  const best = hits.filter(({ label }) => clean(label).length === longest);
  const names = best.filter((h) => h.isName);
  return onlyOne((names.length > 0 ? names : best).map((h) => h.destination));
}

/**
 * The campus building a class location refers to, or null when it is not one we can name for
 * sure (remote, "Room 2001", an unknown code, or two buildings that fit equally well).
 *
 * Order: a building written out by name or alias ("Room 100, York Hall"; the longest wins, so
 * "Price Center East" is not read as something shorter), then a schedule code at the start
 * ("CENTR 115", "AP&M 2402"). A code only counts when it is written like one: in capitals, or
 * followed by a room number. So plain "Price Center" is not read as the code PRICE.
 */
export function matchBuilding(location: string): CampusDestination | null {
  const words = location.split(/[\s,]+/).filter(Boolean);
  if (words.length === 0) return null;

  const written = buildingWrittenOut(` ${clean(location)} `);
  if (written) return written;

  for (let n = 1; n <= Math.min(CODE_WORDS, words.length); n += 1) {
    const candidate = words.slice(0, n).join(' ');
    const followedByRoom = /\d/.test(words[n] ?? '');
    if (candidate !== candidate.toUpperCase() && !followedByRoom) continue;
    const owners = CAMPUS_DESTINATIONS.filter((d) => d.codes?.some((code) => compact(code) === compact(candidate)));
    if (owners.length > 0) return onlyOne(owners);
  }
  return null;
}

/** The planner's arrival fields for a class: its date, and a time that leaves time to walk. */
export function arrivalForClass(session: { date: string; startMinutes: number }): {
  arrivalDate: string;
  arrivalTime: string;
} {
  const minutes = Math.max(0, session.startMinutes - ARRIVE_BEFORE_CLASS_MINUTES);
  return {
    arrivalDate: session.date,
    arrivalTime: `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`,
  };
}
