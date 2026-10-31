/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Link that opens turn-by-turn driving directions to a point in Google Maps (the app on
 * phones, the website elsewhere), starting from the person's current location.
 * Free, no API key. Format: https://developers.google.com/maps/documentation/urls/get-started
 */
export function googleMapsDirectionsUrl(latitude: number, longitude: number): string {
  const params = new URLSearchParams({
    api: '1',
    destination: `${latitude},${longitude}`,
    travelmode: 'driving',
  });
  return `https://www.google.com/maps/dir/?${params.toString()}`;
}
