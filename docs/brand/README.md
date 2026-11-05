# ParkSmart brand

![ParkSmart logo](parksmart-logo-light.svg)

## The mark

A driving route starts at the bottom left, climbs, loops around, and ends on a
gold destination dot. The path traces a **P** without being a letter. The
idea: here is your route, and here is your spot.

## Files

| File | Use |
|---|---|
| `parksmart-mark.svg` | Symbol only (app icon, avatar, favicon source) |
| `parksmart-logo-light.svg` | Symbol + wordmark on white or light backgrounds |
| `parksmart-logo-dark.svg` | Symbol + wordmark on navy or dark backgrounds (white text, invisible on white) |
| `favicon.ico` | Browser favicon (16, 32, 48 px) |
| `parksmart-icon-16.png`, `-32.png`, `-512.png` | Transparent-corner icon PNGs |
| `apple-touch-icon.png` | 180 px full-bleed iOS home-screen icon |

The wordmark is converted to outlines, so the SVGs need no font installed.

## Colors

Sampled from the UC San Diego palette already used by the website
(`frontend/src/index.css`).

| Name | Hex | Where |
|---|---|---|
| Navy | `#182B49` | Tile, "Park" on light backgrounds |
| Gold | `#FFCD00` | Destination dot, "Smart" on dark backgrounds |
| Deep gold | `#C69214` | "Smart" on light backgrounds (bright gold is too faint on white) |
| White | `#FFFFFF` | Route line, "Park" on dark backgrounds |

## Type

Wordmark: **Manrope ExtraBold (800)**, letter spacing −0.03em, two-tone
("Park" + "Smart"). Manrope is free under the SIL Open Font License
([Google Fonts](https://fonts.google.com/specimen/Manrope)).

## Construction (64 × 64 grid)

- Tile: 60 × 60 rounded square, corner radius 14, 2 units of margin.
- Route: 6.8-unit round-capped stroke; the glyph is centered on the tile with
  even padding on all sides.
- Destination dot: radius 6.4 with a 2.8-unit navy ring separating it from
  the route.
- Lockup: symbol height = 64, gap to wordmark = 19, wordmark set at 52 with its
  cap height centered on the tile.

## Do

- Keep the symbol and wordmark at their set proportions; scale the file as a whole.
- Leave clear space around the logo of at least half the tile's width.
- Use the light version on white/light backgrounds and the dark version on navy.

## Don't

- Recolor the route or dot, or swap which half of the name is gold.
- Stretch, rotate, outline, or add shadows.
- Replace the symbol with a plain letter "P".
- Use the UC San Diego wordmark or Triton marks as part of this logo.
