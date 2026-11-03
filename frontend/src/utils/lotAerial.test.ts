import { describe, expect, it } from 'vitest';
import { AERIAL_HEIGHT, AERIAL_WIDTH, lotAerialUrl } from './lotAerial.ts';

const gilman = { latitude: 32.87756239, longitude: -117.23365383, kind: 'structure' as const };

function bboxOf(url: string): number[] {
  return new URL(url).searchParams.get('bbox')!.split(',').map(Number);
}

describe('lotAerialUrl', () => {
  it('asks the USGS NAIP server for a 2x image', () => {
    const url = new URL(lotAerialUrl(gilman));
    expect(url.hostname).toBe('imagery.nationalmap.gov');
    expect(url.searchParams.get('size')).toBe(`${AERIAL_WIDTH * 2},${AERIAL_HEIGHT * 2}`);
    expect(url.searchParams.get('f')).toBe('image');
  });

  it('centers the crop on the lot pin', () => {
    const [xmin, ymin, xmax, ymax] = bboxOf(lotAerialUrl(gilman));
    expect((xmin + xmax) / 2).toBeCloseTo(gilman.longitude, 5);
    expect((ymin + ymax) / 2).toBeCloseTo(gilman.latitude, 5);
  });

  it('shows a wider area for surface lots than for structures', () => {
    const [a, , b] = bboxOf(lotAerialUrl(gilman));
    const [c, , d] = bboxOf(lotAerialUrl({ ...gilman, kind: 'lot' }));
    expect(d - c).toBeGreaterThan(b - a);
  });
});
