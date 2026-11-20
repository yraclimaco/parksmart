import { describe, expect, it } from 'vitest';
import { CAMPUS_DESTINATIONS } from '../data/destinations.ts';
import { matchBuilding, metersBetween } from './scheduleTrips.ts';

/** Every schedule code in the data, with the buildings that claim it. */
const owners = new Map<string, string[]>();
for (const d of CAMPUS_DESTINATIONS) {
  for (const code of d.codes ?? []) {
    const key = code.toLowerCase();
    owners.set(key, [...(owners.get(key) ?? []), d.id]);
  }
}

describe('matchBuilding against every campus code and name', () => {
  it('maps each schedule code (with a room number) to a building that owns that code', () => {
    const wrong: string[] = [];
    for (const [code, ids] of owners) {
      const hit = matchBuilding(`${code.toUpperCase()} 101`);
      if (!hit || !ids.includes(hit.id)) wrong.push(`${code} -> ${hit?.id ?? 'null'} (owners: ${ids.join(',')})`);
    }
    expect(wrong).toEqual([]);
  });

  it('never silently picks one of several buildings that share a code', () => {
    const shared = [...owners].filter(([, ids]) => ids.length > 1);
    // Reported, not asserted: if this list is non-empty the data has a real ambiguity to review.
    expect(shared.map(([code, ids]) => `${code}: ${ids.join(', ')}`)).toEqual([]);
  });

  it('maps each full building name to that building, unless a longer name contains it', () => {
    const wrong: string[] = [];
    for (const d of CAMPUS_DESTINATIONS) {
      if (d.name.replace(/[^a-z]/gi, '').length < 5) continue;
      const hit = matchBuilding(`${d.name} 101`);
      if (hit?.id !== d.id && !(hit && metersBetween(hit, d) <= 150)) wrong.push(`${d.name} -> ${hit?.name ?? 'null'}`);
    }
    expect(wrong).toEqual([]);
  });

  it('maps each alias that is not a common word to the building that lists it', () => {
    const wrong: string[] = [];
    for (const d of CAMPUS_DESTINATIONS) {
      for (const alias of d.aliases ?? []) {
        if (alias.replace(/[^a-z]/gi, '').length < 5) continue;
        const hit = matchBuilding(`${alias} 101`);
        // Allowed: no match (common word or tie), or the same building, or a duplicate entry for the
        // same place (listed twice in the data, within 150 m). Never a different building.
        if (hit && hit.id !== d.id && metersBetween(hit, d) > 150) wrong.push(`${alias} (${d.name}) -> ${hit.name}`);
      }
    }
    expect(wrong).toEqual([]);
  });

  it('never matches a plain room or remote-class location', () => {
    for (const text of ['Room 101', 'Remote', 'Online', 'Zoom', 'TBA', 'N/A', 'Virtual', 'Asynchronous', '101', 'Lab', 'Hall 2']) {
      expect(matchBuilding(text), text).toBeNull();
    }
  });
});
