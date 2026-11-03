/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { ParkingLot } from '../types.ts';

/**
 * Aerial photo of a lot, cropped on demand from USGS NAIP imagery.
 *
 * Source (verified 2026-10-22): USGS The National Map, NAIP orthoimagery ImageServer.
 * Public domain (US government), no API key, CORS open, about 0.3 m per pixel, so
 * individual cars are visible. A request returns exactly the box we ask for.
 * https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer
 *
 * The photo is centered on the lot's pin, which marks the structure's building point
 * or the lot outline's center, so the lot sits in the middle of the frame.
 */
const NAIP_EXPORT_URL =
  'https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer/exportImage';

export const AERIAL_CREDIT = 'USGS NAIP imagery';

/** Displayed size inside the lot card, in CSS pixels. */
export const AERIAL_WIDTH = 340;
export const AERIAL_HEIGHT = 136;

/** Ground width shown, in meters: structures are compact, surface lots spread out. */
const SPAN_METERS = { structure: 190, lot: 250 } as const;

const METERS_PER_DEGREE_LAT = 110_540;
const METERS_PER_DEGREE_LNG_AT_EQUATOR = 111_320;

/**
 * Image URL for a lot's aerial crop. Requested at 2x for sharp retina screens.
 * Pure function so it is easy to test and to swap for real lot photos later.
 */
export function lotAerialUrl(lot: Pick<ParkingLot, 'latitude' | 'longitude' | 'kind'>, scale = 2): string {
  const widthMeters = SPAN_METERS[lot.kind === 'lot' ? 'lot' : 'structure'];
  const heightMeters = (widthMeters * AERIAL_HEIGHT) / AERIAL_WIDTH;
  const dLng = widthMeters / 2 / (METERS_PER_DEGREE_LNG_AT_EQUATOR * Math.cos((lot.latitude * Math.PI) / 180));
  const dLat = heightMeters / 2 / METERS_PER_DEGREE_LAT;
  const bbox = [lot.longitude - dLng, lot.latitude - dLat, lot.longitude + dLng, lot.latitude + dLat]
    .map((n) => n.toFixed(6))
    .join(',');
  const params = new URLSearchParams({
    bbox,
    bboxSR: '4326',
    imageSR: '3857',
    size: `${AERIAL_WIDTH * scale},${AERIAL_HEIGHT * scale}`,
    format: 'jpg',
    f: 'image',
  });
  return `${NAIP_EXPORT_URL}?${params.toString()}`;
}

const preloaded = new Set<string>();

/** Starts downloading a lot's photo (e.g. on pin hover) so the card opens with it ready. */
export function preloadLotAerial(lot: Pick<ParkingLot, 'latitude' | 'longitude' | 'kind'>): void {
  const url = lotAerialUrl(lot);
  if (preloaded.has(url) || typeof Image === 'undefined') return;
  preloaded.add(url);
  const img = new Image();
  img.decoding = 'async';
  img.src = url;
}
