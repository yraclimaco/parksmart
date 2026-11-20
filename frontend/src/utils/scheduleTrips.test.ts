import { describe, expect, it } from 'vitest';
import { ARRIVE_BEFORE_CLASS_MINUTES, arrivalForClass, formatClock, matchBuilding, metersBetween } from './scheduleTrips.ts';

describe('matchBuilding', () => {
  it('matches a UCSD class-schedule code at the start of the location', () => {
    expect(matchBuilding('CENTR 115')?.id).toBe('center-hall');
    expect(matchBuilding('WLH 2001')?.id).toBe('warren-lecture-hall');
    expect(matchBuilding('PCYNH 106')?.id).toBe('pepper-canyon-hall');
    expect(matchBuilding('peter 108')?.id).toBe('peterson-hall');
  });

  it('matches codes and aliases written with punctuation', () => {
    expect(matchBuilding('APM B402')?.id).toBe('applied-physics-and-mathematics');
    expect(matchBuilding('AP&M 2402')?.id).toBe('applied-physics-and-mathematics');
  });

  it('matches a building named in full', () => {
    expect(matchBuilding('York Hall 2722')?.id).toBe('york-hall');
    expect(matchBuilding('Room 100, Warren Lecture Hall')?.id).toBe('warren-lecture-hall');
  });

  it('reads a full name as the building even when its first word is another building\'s code', () => {
    // PRICE is the schedule code of Price Center West, but this is East
    expect(matchBuilding('Price Center East 101')?.id).toBe('price-center-east');
    expect(matchBuilding('Price Center West')?.id).toBe('price-center-west');
    expect(matchBuilding('Recreation Gymnasium')?.id).toBe('recreation-gymnasium');
  });

  it('does not read a plain word as a schedule code', () => {
    // PRICE is West's code, but a lone lowercase "price" is just a word
    expect(matchBuilding('price')).toBeNull();
    // "Price Center" is listed in the data as another name for Price Center East, so it is that,
    // matched by name and not by the code PRICE (which would have meant West)
    expect(matchBuilding('Price Center')?.id).toBe('price-center-east');
  });

  it('accepts a lowercase code only when a room number follows', () => {
    expect(matchBuilding('peter 108')?.id).toBe('peterson-hall');
    expect(matchBuilding('peter')).toBeNull();
  });

  it('matches another name for a building', () => {
    expect(matchBuilding('Calit2 101')?.id).toBe('atkinson-hall');
    expect(matchBuilding('Ledden Auditorium 101')?.id).toBe('humanities-and-social-sciences');
  });

  it('does not let a common one-word alias claim every building that shares the word', () => {
    // The data gives a far-off forum the alias "Auditorium"; that must not pull other auditoriums to it
    expect(matchBuilding('Mandeville Auditorium')).toBeNull();
    expect(matchBuilding('Random Auditorium 101')).toBeNull();
  });

  it('returns null for unknown, remote or empty locations', () => {
    expect(matchBuilding('')).toBeNull();
    expect(matchBuilding('Remote')).toBeNull();
    expect(matchBuilding('Zoom')).toBeNull();
    expect(matchBuilding('Room 2001')).toBeNull();
  });
});

describe('arrivalForClass', () => {
  it('arrives a set time before the class starts', () => {
    expect(arrivalForClass({ date: '2026-11-18', startMinutes: 9 * 60 + 30 })).toEqual({
      arrivalDate: '2026-11-18',
      arrivalTime: '09:10',
    });
    expect(ARRIVE_BEFORE_CLASS_MINUTES).toBe(20);
  });

  it('never goes before midnight', () => {
    expect(arrivalForClass({ date: '2026-11-18', startMinutes: 10 })).toEqual({
      arrivalDate: '2026-11-18',
      arrivalTime: '00:00',
    });
  });
});

describe('formatClock', () => {
  it('formats minutes as a 12-hour clock', () => {
    expect(formatClock(0)).toBe('12:00 AM');
    expect(formatClock(9 * 60 + 5)).toBe('9:05 AM');
    expect(formatClock(12 * 60)).toBe('12:00 PM');
    expect(formatClock(13 * 60 + 30)).toBe('1:30 PM');
  });
});

describe('buildings listed twice, and buildings far apart', () => {
  it('treats duplicate entries for one place as that place', () => {
    // "Faculty Club" is a building and also an alias of the Ida and Cecil Green Faculty Club, 43 m away
    expect(matchBuilding('Faculty Club')?.id).toBe('faculty-club');
  });

  it('keeps a longer name from being read as a shorter building inside it', () => {
    expect(matchBuilding('Institute of the Americas Building 101')?.id).toBe('institute-of-the-americas-building');
    expect(matchBuilding('LionTree Arena 101')?.id).toBe('rimac');
  });

  it('measures distance in meters', () => {
    const a = { latitude: 32.87957, longitude: -117.23958 };
    const b = { latitude: 32.87919, longitude: -117.23952 };
    expect(metersBetween(a, b)).toBeGreaterThan(40);
    expect(metersBetween(a, b)).toBeLessThan(46);
    expect(metersBetween(a, a)).toBe(0);
  });
});
