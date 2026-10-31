/**
 * Sanity checks for the campus destination list pulled from UCSD's GIS, and for
 * the search that powers the destination box.
 */

import { describe, expect, it } from 'vitest';
import {
  CAMPUS_DESTINATIONS,
  DEFAULT_DESTINATION_ID,
  POPULAR_DESTINATIONS,
  findDestination,
  getDestination,
  makePinDestinationId,
  searchDestinations,
} from './destinations.ts';

describe('CAMPUS_DESTINATIONS', () => {
  it('has unique IDs and names', () => {
    expect(new Set(CAMPUS_DESTINATIONS.map((d) => d.id)).size).toBe(CAMPUS_DESTINATIONS.length);
    expect(new Set(CAMPUS_DESTINATIONS.map((d) => d.name)).size).toBe(CAMPUS_DESTINATIONS.length);
  });

  it('includes the fallback destination', () => {
    expect(CAMPUS_DESTINATIONS.some((d) => d.id === DEFAULT_DESTINATION_ID)).toBe(true);
  });

  it('keeps every destination near the La Jolla campus (incl. Scripps pier and Torrey Pines Center)', () => {
    for (const d of CAMPUS_DESTINATIONS) {
      expect(d.latitude).toBeGreaterThan(32.86);
      expect(d.latitude).toBeLessThan(32.895);
      expect(d.longitude).toBeGreaterThan(-117.26);
      expect(d.longitude).toBeLessThan(-117.215);
    }
  });

  it('covers all 24 general-assignment classroom codes from facilities.ucsd.edu', () => {
    const codes = new Set(CAMPUS_DESTINATIONS.flatMap((d) => d.codes ?? []));
    for (const code of ['APM', 'MALK', 'CTL', 'CENTR', 'COA', 'CSB', 'CICC', 'FAH', 'GH', 'HSS', 'LEDDN', 'MANDE',
      'MCGIL', 'MOS', 'PCYNH', 'PETER', 'PODEM', 'PRICE', 'RWAC', 'RBC', 'SSB', 'SOLIS', 'WLH', 'YORK']) {
      expect(codes.has(code)).toBe(true);
    }
  });

  it('lists popular places in a fixed order starting with Geisel Library', () => {
    expect(POPULAR_DESTINATIONS.length).toBeGreaterThan(20);
    expect(POPULAR_DESTINATIONS[0].name).toBe('Geisel Library');
    const order = POPULAR_DESTINATIONS.map((d) => d.popular);
    expect([...order].sort((a, b) => a! - b!)).toEqual(order);
  });
});

describe('searchDestinations', () => {
  const top = (q: string) => searchDestinations(q)[0]?.destination.name;

  it('puts an exact class-schedule code first', () => {
    expect(top('WLH')).toBe('Warren Lecture Hall');
    expect(top('pcynh')).toBe('Pepper Canyon Hall');
    expect(top('CENTR')).toBe('Center Hall');
    expect(searchDestinations('LEDDN')[0]).toMatchObject({
      destination: { name: 'Humanities and Social Sciences' },
      matchedOn: 'LEDDN',
    });
  });

  it('matches names by prefix and by word', () => {
    expect(top('geisel')).toBe('Geisel Library');
    expect(searchDestinations('lecture').map((m) => m.destination.name)).toContain('Warren Lecture Hall');
  });

  it('matches other names and says which one matched', () => {
    const match = searchDestinations('ledden auditorium')[0];
    expect(match.destination.name).toBe('Humanities and Social Sciences');
    expect(match.matchedOn).toBe('Ledden Auditorium');
    expect(top('calit2')).toBe('Atkinson Hall');
  });

  it('ignores punctuation like AP&M', () => {
    expect(top('ap&m')).toBe('Applied Physics and Mathematics');
  });

  it('returns nothing for an empty query', () => {
    expect(searchDestinations('   ')).toEqual([]);
  });
});

describe('dropped pins', () => {
  it('round-trips a map tap through a string ID', () => {
    const id = makePinDestinationId(32.880123, -117.237111);
    expect(id).toBe('pin:32.88012,-117.23711');
    expect(findDestination(id)).toMatchObject({ name: 'Dropped pin', latitude: 32.88012, longitude: -117.23711, isPin: true });
  });

  it('treats unknown or empty IDs as no destination', () => {
    expect(findDestination('')).toBeUndefined();
    expect(findDestination('pin:abc')).toBeUndefined();
    expect(getDestination('nope').id).toBe(DEFAULT_DESTINATION_ID);
  });
});
