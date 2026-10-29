/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { motion } from 'motion/react';
import { Clock, MapPin, MapPinOff } from 'lucide-react';
import * as maplibregl from 'maplibre-gl';
// MapLibre draws tiles in a background Web Worker. Vite bundles the main library
// but does not copy the worker file, so the default worker URL 404s and the map
// renders blank. `?url` makes Vite emit the worker as an asset and give us its URL.
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
import {
  MAP_CONFIG,
  MAP_PADDING,
  OPENFREEMAP_POSITRON_STYLE_URL,
  SATELLITE_STYLE,
  DEFAULT_BASEMAP,
  BasemapMode,
} from '../constants.ts';
import { ParkingLot, CampusDestination } from '../types.ts';
import { availabilityStatus } from '../utils/availability.ts';
import { availabilityAt } from '../utils/availabilityModel.ts';
import { preloadLotAerial } from '../utils/lotAerial.ts';
import { layoutPins, PinItem, Rect } from '../utils/labelLayout.ts';

// Must run before the first map is created.
maplibregl.setWorkerUrl(maplibreWorkerUrl);
// Start the tile workers now, so they download in parallel with React mounting
// instead of after the map is created.
maplibregl.prewarm();

/** Returns the MapLibre style for a basemap mode. */
function styleFor(mode: BasemapMode): string | maplibregl.StyleSpecification {
  return mode === 'satellite'
    ? (SATELLITE_STYLE as unknown as maplibregl.StyleSpecification)
    : OPENFREEMAP_POSITRON_STYLE_URL;
}

/** Escapes text placed into marker HTML (building names can contain "&"). */
function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

/** Height of the bottom strip covered by the lot detail card (card + aerial photo + margins). */
const DETAIL_CARD_INSET_PX = 520;

/**
 * Pin sizes step down as the map zooms out (see .ps-zoom-far / .ps-zoom-mid in index.css),
 * and labelLayout decides which names and surface lots still fit at each zoom.
 */
const ZOOM_FAR = 14.6;
const ZOOM_MID = 15.6;
type ZoomTier = 'far' | 'mid' | 'near';
function zoomTier(zoom: number): ZoomTier {
  return zoom < ZOOM_FAR ? 'far' : zoom < ZOOM_MID ? 'mid' : 'near';
}
/** Disc radius and label start (px below the pin center) per tier; must match index.css. */
const DISC_RADIUS: Record<ZoomTier, { structure: number; lot: number }> = {
  far: { structure: 9, lot: 6 },
  mid: { structure: 11, lot: 8 },
  near: { structure: 13, lot: 10 },
};
const LABEL_OFFSET: Record<ZoomTier, { structure: number; lot: number }> = {
  far: { structure: 13, lot: 10 },
  mid: { structure: 15, lot: 12 },
  near: { structure: 17, lot: 14 },
};
const RANKED_RADIUS = 13;
const RANKED_LABEL_OFFSET = 17;
const SELECTED_LABEL_OFFSET = 8;
const SELECTED_RADIUS = 21;
/** Distance from the selected pin's point up to the center of its balloon head. */
const SELECTED_BODY_SHIFT = 27;
const PIN_PRIORITY = { selected: 100, first: 90, backup: 80, third: 70, structure: 10, lot: 0 };
const TAG_WIDTH: Record<string, number> = { first: 84, backup: 56, third: 28 };

/** Pin drop-in timing; must match the .pin-drop duration in index.css. */
const PIN_DROP_DURATION_MS = 420;
const PIN_DROP_BASE_DELAY_MS = 120;
const PIN_DROP_STAGGER_MS = 40;

/** Shortens "Gilman Parking Structure" to "Gilman" for compact map pins. */
function pinLabel(name: string): string {
  return name.replace(' Parking Structure', '');
}

/**
 * Empty MapLibre control used as a mount point for the React Map/Satellite toggle.
 * Registering it as a real control puts it in the same top-right row as the zoom
 * and compass buttons, so MapLibre handles alignment and spacing for us.
 */
class ReactMountControl implements maplibregl.IControl {
  readonly container = document.createElement('div');
  onAdd(): HTMLElement {
    this.container.className = 'maplibregl-ctrl';
    return this.container;
  }
  onRemove(): void {
    this.container.remove();
  }
}

/** Shared look of the single-button map controls (Time, Drop pin). */
const CONTROL_BUTTON = 'ps-control-btn';

const BASEMAP_OPTIONS: Array<{ mode: BasemapMode; label: string }> = [
  { mode: 'map', label: 'Map' },
  { mode: 'satellite', label: 'Satellite' },
];

interface MapContainerProps {
  lots: ParkingLot[];
  selectedLocationId: string | null;
  selectedDestination: CampusDestination | null;
  onSelectLot: (locationId: string) => void;
  onClearSelection: () => void;
  /**
   * Called when the map is clicked while "Drop pin" is on. Returns whether the spot was
   * accepted (false when it is off campus, so the tool stays on for another try).
   */
  onDropPin: (latitude: number, longitude: number) => boolean;
  /** A dropped pin is currently the destination; the Drop pin button then removes it. */
  hasDroppedPin: boolean;
  onClearPin: () => void;
  /** Time tool: the toggle sits in the map's control row and its panel opens beneath it. */
  isTimeOpen: boolean;
  onTimeToggle: () => void;
  timePanel: React.ReactNode;
  /** Whether the left planner panel is showing; controls how much map is covered. */
  isPanelOpen: boolean;
  /** Whether the lot detail card is showing at the bottom of the map. */
  isDetailOpen: boolean;
  /** Current first choice / backup, labeled on the map. */
  rankedLotIds: { first: string | null; backup: string | null; third: string | null };
  /** Time the pins' availability colors represent (the time scrubber). */
  availabilityTime: Date;
}

/**
 * Interactive full-screen map rendered with MapLibre GL and OpenFreeMap Positron vector tiles.
 * Supports custom DOM markers, smooth flyTo camera glides, and responsive panel offset framing.
 */
export const MapContainer: React.FC<MapContainerProps> = ({
  lots,
  selectedLocationId,
  selectedDestination,
  onSelectLot,
  onClearSelection,
  onDropPin,
  hasDroppedPin,
  onClearPin,
  isTimeOpen,
  onTimeToggle,
  timePanel,
  isPanelOpen,
  isDetailOpen,
  rankedLotIds,
  availabilityTime,
}) => {
  const availabilityTimeRef = useRef(availabilityTime);
  availabilityTimeRef.current = availabilityTime;
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const lotMarkersRef = useRef<Map<string, maplibregl.Marker>>(new Map());
  const destinationMarkerRef = useRef<maplibregl.Marker | null>(null);
  const onDropPinRef = useRef(onDropPin);
  onDropPinRef.current = onDropPin;
  const lotsRef = useRef(lots);
  lotsRef.current = lots;
  const destinationRef = useRef(selectedDestination);
  destinationRef.current = selectedDestination;
  // Drop pin tool: off by default; while on, the next map click sets the destination
  const [isPinMode, setIsPinMode] = useState(false);
  const isPinModeRef = useRef(false);
  isPinModeRef.current = isPinMode;
  const [pinMessage, setPinMessage] = useState<string | null>(null);
  const hasSelectionRef = useRef(false);
  hasSelectionRef.current = selectedLocationId !== null || isDetailOpen;
  const isLoadedRef = useRef<boolean>(false);
  const [basemap, setBasemap] = useState<BasemapMode>(DEFAULT_BASEMAP);
  // Placeholder shown until the first tiles have drawn (or a few seconds pass)
  const [isMapReady, setIsMapReady] = useState(false);
  const [basemapControlEl, setBasemapControlEl] = useState<HTMLElement | null>(null);

  // Map padding: reserve the panel's width on the left only while it is open.
  // Clamped to half the window so a narrow window can't produce an impossible camera.
  const viewportWidth = typeof window === 'undefined' ? 1440 : window.innerWidth;
  const viewportHeight = typeof window === 'undefined' ? 800 : window.innerHeight;
  // Phone: the planner is a bottom sheet over the lower half, so reserve the bottom, not the left
  const isNarrow = viewportWidth < 640;
  const padding = isNarrow
    ? {
        top: 40,
        right: 24,
        left: 24,
        bottom: isDetailOpen
          ? Math.min(DETAIL_CARD_INSET_PX, viewportHeight * 0.6)
          : isPanelOpen
          ? viewportHeight * 0.5 + 60
          : 100,
      }
    : {
        ...MAP_PADDING,
        // While the lot card is open, treat the strip it covers as hidden too
        bottom: isDetailOpen ? DETAIL_CARD_INSET_PX : MAP_PADDING.bottom,
        left: isPanelOpen ? Math.min(MAP_PADDING.left, viewportWidth / 2) : MAP_PADDING.right,
      };
  const paddingRef = useRef(padding);
  paddingRef.current = padding;

  // Declutter: size pins for the zoom, then hide crowded surface lots and names that would
  // overlap something more important. Runs on zoom/resize and whenever pins change.
  const applyLayoutRef = useRef<() => void>(() => {});
  applyLayoutRef.current = () => {
    const map = mapRef.current;
    if (!map) return;
    const tier = zoomTier(map.getZoom());
    const container = map.getContainer();
    container.classList.toggle('ps-zoom-far', tier === 'far');
    container.classList.toggle('ps-zoom-mid', tier === 'mid');

    const items: PinItem[] = [];
    for (const lot of lotsRef.current) {
      const marker = lotMarkersRef.current.get(lot.locationId);
      if (!marker) continue;
      const el = marker.getElement();
      const rank = el.dataset.rank || '';
      const isSelected = el.dataset.selected === '1';
      const isLot = lot.kind === 'lot';
      const point = map.project(marker.getLngLat());
      // The selected balloon rises above its point, so treat its body as the disc
      const shiftUp = isSelected ? SELECTED_BODY_SHIFT : 0;
      const nameW = pinLabel(lot.name).length * (isSelected ? 7.6 : 6.8) + 6;
      const tagW = TAG_WIDTH[rank] ?? 0;
      items.push({
        id: lot.locationId,
        cx: point.x,
        cy: point.y - shiftUp,
        radius: isSelected ? SELECTED_RADIUS : rank ? RANKED_RADIUS : isLot ? DISC_RADIUS[tier].lot : DISC_RADIUS[tier].structure,
        labelW: Math.max(nameW, tagW),
        labelH: (isSelected ? 17 : 15) + (tagW > 0 ? 19 : 0),
        labelOffset: isSelected
          ? SELECTED_LABEL_OFFSET + shiftUp
          : rank
          ? RANKED_LABEL_OFFSET
          : isLot
          ? LABEL_OFFSET[tier].lot
          : LABEL_OFFSET[tier].structure,
        tagW,
        tagH: 15,
        priority: isSelected
          ? PIN_PRIORITY.selected
          : rank === 'first' || rank === 'backup' || rank === 'third'
          ? PIN_PRIORITY[rank]
          : isLot
          ? PIN_PRIORITY.lot
          : PIN_PRIORITY.structure,
        pinned: isSelected || rank !== '',
        droppable: isLot,
        forceName: isSelected,
      });
    }

    // The destination's name pill hangs above its point; names should not sit under it
    const obstacles: Rect[] = [];
    const destination = destinationRef.current;
    if (destination) {
      const p = map.project([destination.longitude, destination.latitude]);
      const w = Math.min(260, destination.name.length * 7 + 44);
      obstacles.push({ x: p.x - w / 2, y: p.y - 46, w, h: 46 });
    }

    const { hidden, labels, above } = layoutPins(items, obstacles);
    for (const lot of lotsRef.current) {
      const el = lotMarkersRef.current.get(lot.locationId)?.getElement();
      if (!el) continue;
      el.classList.toggle('ps-hidden', hidden.has(lot.locationId));
      el.dataset.label = labels.get(lot.locationId) ?? 'none';
      el.classList.toggle('ps-label-above', above.has(lot.locationId));
    }
  };
  const layoutFrameRef = useRef<number | null>(null);
  const scheduleLayout = useCallback(() => {
    if (layoutFrameRef.current !== null) return;
    layoutFrameRef.current = requestAnimationFrame(() => {
      layoutFrameRef.current = null;
      applyLayoutRef.current();
    });
  }, []);

  // Helper to frame all lots plus the destination with panel offset padding
  const frameAllPoints = (map: maplibregl.Map, animate = true) => {
    if (lots.length === 0) return;

    const bounds = new maplibregl.LngLatBounds();
    lots.forEach((lot) => bounds.extend([lot.longitude, lot.latitude]));
    if (selectedDestination) {
      bounds.extend([selectedDestination.longitude, selectedDestination.latitude]);
    }

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    map.fitBounds(bounds, {
      padding: paddingRef.current,
      maxZoom: 16.0,
      duration: !animate || prefersReducedMotion ? 0 : 600,
    });
  };

  // Initialize MapLibre instance with OpenFreeMap Positron style
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: styleFor(DEFAULT_BASEMAP),
      center: MAP_CONFIG.DEFAULT_CENTER,
      zoom: MAP_CONFIG.DEFAULT_ZOOM,
      minZoom: MAP_CONFIG.MIN_ZOOM,
      maxZoom: MAP_CONFIG.MAX_ZOOM,
      attributionControl: false,
    });

    // Top-right row: Map/Satellite toggle first (left), then zoom + compass (right).
    // The toggle itself is rendered by React into this control via a portal below.
    const basemapControl = new ReactMountControl();
    map.addControl(basemapControl, 'top-right');
    setBasemapControlEl(basemapControl.container);

    map.addControl(
      new maplibregl.NavigationControl({
        showCompass: true,
        showZoom: true,
        visualizePitch: false,
      }),
      'top-right'
    );

    // Add OpenFreeMap & OpenStreetMap attribution in bottom right
    map.addControl(
      new maplibregl.AttributionControl({
        compact: true,
      }),
      'bottom-right'
    );

    map.on('zoom', scheduleLayout);
    map.on('resize', scheduleLayout);
    scheduleLayout();

    map.once('idle', () => setIsMapReady(true));
    const readyTimer = window.setTimeout(() => setIsMapReady(true), 6000);

    // On initial map style load, fit bounds to all lots plus the destination
    map.on('load', () => {
      isLoadedRef.current = true;
      frameAllPoints(map, false);
      scheduleLayout();
    });

    // Clicking the map background. With Drop pin on, the click sets the destination.
    // Otherwise it just closes an open lot card (nothing pops up on a plain click).
    map.on('click', (e) => {
      const target = e.originalEvent.target as HTMLElement;
      if (target.closest('.parksmart-marker')) return;
      if (isPinModeRef.current) {
        const accepted = onDropPinRef.current(e.lngLat.lat, e.lngLat.lng);
        if (accepted) {
          setIsPinMode(false);
          setPinMessage(null);
        } else {
          setPinMessage('That spot is off campus. Try again on campus.');
        }
        return;
      }
      if (hasSelectionRef.current) onClearSelection();
    });

    mapRef.current = map;

    return () => {
      window.clearTimeout(readyTimer);
      if (layoutFrameRef.current !== null) cancelAnimationFrame(layoutFrameRef.current);
      layoutFrameRef.current = null;
      map.remove();
      mapRef.current = null;
      isLoadedRef.current = false;
    };
  }, [onClearSelection, scheduleLayout]);

  // Update or render destination marker
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (destinationMarkerRef.current) {
      destinationMarkerRef.current.remove();
      destinationMarkerRef.current = null;
    }

    if (selectedDestination) {
      const el = document.createElement('div');
      el.className = 'parksmart-destination-pin flex flex-col items-center pointer-events-none select-none z-10';
      el.innerHTML = `
        <div class="px-2.5 py-1 bg-[#182B49] text-white text-[12px] font-semibold rounded-md shadow-md border border-white/40 flex items-center gap-1.5 whitespace-nowrap mb-1">
          <svg class="w-3 h-3 text-[#FFCD00]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
            <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
          </svg>
          <span>${escapeHtml(selectedDestination.name)}</span>
        </div>
        <div class="w-3 h-3 rounded-full bg-[#FFCD00] border-2 border-[#182B49] shadow"></div>
      `;

      // Under every pin (they are 1 to 4), so a pin disc is never hidden behind its name pill
      el.style.zIndex = '0';

      const marker = new maplibregl.Marker({
        element: el,
        anchor: 'bottom',
      })
        .setLngLat([selectedDestination.longitude, selectedDestination.latitude])
        .addTo(map);

      destinationMarkerRef.current = marker;
    }
    scheduleLayout();
  }, [selectedDestination, scheduleLayout]);

  // When the user picks a different destination, show the whole picture again.
  // (Only on destination changes, never on lot select/deselect.)
  const lastDestinationIdRef = useRef<string | undefined>(selectedDestination?.id);
  useEffect(() => {
    const map = mapRef.current;
    const destinationId = selectedDestination?.id;
    if (destinationId === lastDestinationIdRef.current) return;
    lastDestinationIdRef.current = destinationId;
    // A dropped pin is already where the user is looking; only reframe for picked places
    if (map && isLoadedRef.current && selectedDestination && !selectedDestination.isPin) frameAllPoints(map, true);
  }, [selectedDestination]);

  // Render and update parking lot markers
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    // Clean up markers that are no longer in lots list
    const currentLotIds = new Set(lots.map((l) => l.locationId));
    lotMarkersRef.current.forEach((marker, id) => {
      if (!currentLotIds.has(id)) {
        marker.remove();
        lotMarkersRef.current.delete(id);
      }
    });

    // Create or refresh markers
    lots.forEach((lot, index) => {
      const isSelected = selectedLocationId === lot.locationId;
      const rank =
        lot.locationId === rankedLotIds.first
          ? 'first'
          : lot.locationId === rankedLotIds.backup
          ? 'backup'
          : lot.locationId === rankedLotIds.third
          ? 'third'
          : null;
      let marker = lotMarkersRef.current.get(lot.locationId);

      // Create new marker if not exists
      if (!marker) {
        const el = document.createElement('div');
        el.className = 'parksmart-marker';
        // Staggered drop-in when pins first appear (see .pin-drop in index.css)
        el.dataset.createdAt = String(performance.now());
        el.dataset.dropDelay = String(PIN_DROP_BASE_DELAY_MS + index * PIN_DROP_STAGGER_MS);
        el.setAttribute('role', 'button');
        el.setAttribute('tabindex', '0');
        el.setAttribute('aria-label', `Parking Lot ${lot.name}, ${lot.estimatedAvailabilityPercent}% estimated capacity`);

        el.addEventListener('click', (e) => {
          e.stopPropagation();
          onSelectLot(lot.locationId);
        });

        // Hovered pin rises above overlapping neighbors so it can be clicked
        el.addEventListener('mouseenter', () => {
          el.style.zIndex = '4';
          preloadLotAerial(lot); // card opens with its photo already downloading
        });
        el.addEventListener('mouseleave', () => {
          el.style.zIndex = el.dataset.baseZ ?? '1';
        });

        el.addEventListener('keydown', (e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            e.stopPropagation();
            onSelectLot(lot.locationId);
          }
        });

        // 'center' anchors the 0x0 marker element exactly on the coordinate
        marker = new maplibregl.Marker({
          element: el,
          anchor: 'center',
        })
          .setLngLat([lot.longitude, lot.latitude])
          .addTo(map);

        lotMarkersRef.current.set(lot.locationId, marker);
      }

      // Update marker element styling and contents
      const el = marker.getElement();
      // Explicit z-index on every pin (its own stacking context) so the selected or
      // hovered pin reliably stacks above overlapping neighbors like Gilman/Triton.
      // Stacking: selected (3) > first choice/backup (2) > others (1); hover raises to 4
      el.dataset.baseZ = isSelected ? '3' : rank ? '2' : '1';
      el.style.zIndex = el.dataset.baseZ;
      el.setAttribute('aria-pressed', String(isSelected));
      // Label style follows the basemap: white-on-dark for satellite, dark-on-light for map.
      // A class flip is enough; no need to rebuild the pin.
      el.classList.toggle('ps-on-light', basemap === 'map');
      el.classList.toggle('ps-selected', isSelected);
      el.classList.toggle('ps-ranked', rank !== null);
      el.classList.toggle('ps-first', rank === 'first');
      el.classList.toggle('ps-backup', rank === 'backup');
      el.classList.toggle('ps-lot', lot.kind === 'lot');
      el.dataset.rank = rank ?? '';
      el.dataset.selected = isSelected ? '1' : '0';

      // Rebuild the pin's HTML only when its selected state or rank actually changed
      // (usually 1 or 2 pins per click, not all of them).
      const renderKey = `${isSelected}|${rank}`;
      if (el.dataset.renderKey === renderKey) return;
      el.dataset.renderKey = renderKey;

      const avail = `<span class="ps-avail" style="background:${availabilityStatus(availabilityAt(lot, availabilityTimeRef.current)).color}"></span>`;
      const rankTag =
        rank === 'first'
          ? '<span class="ps-rank ps-rank-first">First choice</span>'
          : rank === 'backup'
          ? '<span class="ps-rank ps-rank-backup">Backup</span>'
          : rank === 'third'
          ? '<span class="ps-rank ps-rank-backup">#3</span>'
          : '';
      const label = `<span class="ps-label"><span class="ps-name">${pinLabel(lot.name)}</span>${rankTag}</span>`;

      // If the pin is rebuilt while its drop-in is still playing, offset the delay by the
      // time already elapsed; a negative delay resumes the animation part-way through.
      const elapsed = performance.now() - Number(el.dataset.createdAt);
      const remainingDelay = Number(el.dataset.dropDelay) - elapsed;
      const stillDropping = remainingDelay + PIN_DROP_DURATION_MS > 0;

      el.innerHTML = `
        <div class="${stillDropping ? 'pin-drop' : ''}" style="position:absolute;left:0;top:0;animation-delay:${Math.round(remainingDelay)}ms">
          ${
            isSelected
              ? `<span class="ps-ground"></span>
                 <span class="ps-balloon">
                   <span class="ps-balloon-head">P${avail}</span>
                   <span class="ps-balloon-tail"></span>
                 </span>`
              : `<span class="ps-glyph">P${avail}</span>`
          }
          ${label}
        </div>
      `;
    });
    scheduleLayout();
  }, [lots, selectedLocationId, onSelectLot, basemap, rankedLotIds, scheduleLayout]);

  // Time scrubber: recolor each pin's availability dot in place (no pin rebuilds)
  useEffect(() => {
    for (const lot of lots) {
      const dot = lotMarkersRef.current.get(lot.locationId)?.getElement().querySelector<HTMLElement>('.ps-avail');
      if (dot) dot.style.background = availabilityStatus(availabilityAt(lot, availabilityTime)).color;
    }
  }, [availabilityTime, lots]);

  // Drop pin tool: crosshair cursor while on, Esc turns it off, and the hint clears itself
  useEffect(() => {
    const map = mapRef.current;
    if (map) map.getCanvas().style.cursor = isPinMode ? 'crosshair' : '';
    if (!isPinMode) {
      setPinMessage(null);
      return;
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsPinMode(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isPinMode]);
  useEffect(() => {
    if (!pinMessage) return;
    const timer = window.setTimeout(() => setPinMessage(null), 3500);
    return () => window.clearTimeout(timer);
  }, [pinMessage]);

  // Swap basemap when the toggle changes. DOM markers are unaffected by setStyle.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isLoadedRef.current) return;
    map.setStyle(styleFor(basemap));
  }, [basemap]);

  // Selecting a lot: if its pin is hidden (off screen or under the panel), glide it
  // into view. Zoom is never changed. Deselecting never moves the camera.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isLoadedRef.current || !selectedLocationId) return;

    const targetLot = lots.find((l) => l.locationId === selectedLocationId);
    if (!targetLot) return;

    const point = map.project([targetLot.longitude, targetLot.latitude]);
    const { width, height } = map.getContainer().getBoundingClientRect();
    const pad = paddingRef.current;
    const isVisible =
      point.x >= pad.left && point.x <= width - pad.right &&
      point.y >= pad.top && point.y <= height - pad.bottom;
    if (isVisible) return;

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    map.easeTo({
      center: [targetLot.longitude, targetLot.latitude],
      padding: pad,
      duration: prefersReducedMotion ? 0 : MAP_CONFIG.FLY_DURATION_MS,
    });
  }, [selectedLocationId, lots]);

  // Opening/closing the panel only shifts the map's visual center; zoom stays put.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isLoadedRef.current) return;
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    map.easeTo({ padding: paddingRef.current, duration: prefersReducedMotion ? 0 : 300 });
  }, [isPanelOpen]);

  return (
    <>
      <div
        ref={mapContainerRef}
        className="absolute inset-0 w-full h-full bg-[#f8f9fa] z-0 focus:outline-none"
        aria-label="Interactive UCSD Campus Parking Map"
      />

      {/* Placeholder while map tiles load, so the first seconds are not a blank screen */}
      <div
        aria-hidden={isMapReady}
        className={`absolute inset-0 z-[1] flex items-center justify-center bg-slate-100 pointer-events-none transition-opacity duration-500 ${
          isMapReady ? 'opacity-0' : 'opacity-100'
        }`}
      >
        <div role="status" className="flex items-center gap-2 text-xs font-medium text-muted">
          <span className="w-4 h-4 border-2 border-slate-300 border-t-slate-600 rounded-full animate-spin" />
          {isMapReady ? '' : 'Loading map...'}
        </div>
      </div>

      {/* Map controls, mounted inside the map's top-right control row (left of zoom):
          row 1 is Time + Map/Satellite, row 2 is Drop pin right under Map/Satellite.
          Every button is 34px tall so the rows line up. */}
      {basemapControlEl &&
        createPortal(
          <div className="relative flex flex-col items-end gap-2">
            <div className="flex items-start gap-2">
              <button
                type="button"
                aria-pressed={isTimeOpen}
                aria-expanded={isTimeOpen}
                onClick={onTimeToggle}
                className={CONTROL_BUTTON}
                data-tone="navy"
              >
                <Clock className="w-4 h-4" aria-hidden="true" />
                Time
              </button>
              <div
                role="radiogroup"
                aria-label="Map style"
                className="flex h-[34px] p-[2px] rounded-[10px] bg-white border border-line shadow-[0_1px_2px_rgba(24,43,73,0.08),0_4px_12px_rgba(24,43,73,0.1)]"
              >
                {BASEMAP_OPTIONS.map(({ mode, label }) => (
                  <button
                    key={mode}
                    type="button"
                    role="radio"
                    aria-checked={basemap === mode}
                    onClick={() => setBasemap(mode)}
                    className={`relative h-[28px] px-3 text-xs font-semibold rounded-[8px] transition-colors duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky/40 cursor-pointer ${
                      basemap === mode ? 'text-white' : 'text-muted hover:text-navy'
                    }`}
                  >
                    {basemap === mode && (
                      <motion.span
                        layoutId="basemap-thumb"
                        className="absolute inset-0 rounded-[8px] bg-navy"
                        transition={{ type: 'spring', stiffness: 500, damping: 35 }}
                      />
                    )}
                    <span className="relative">{label}</span>
                  </button>
                ))}
              </div>
            </div>

            <button
              type="button"
              aria-pressed={isPinMode || hasDroppedPin}
              onClick={() => {
                if (hasDroppedPin) {
                  onClearPin();
                  setIsPinMode(false);
                } else {
                  setIsPinMode((on) => !on);
                }
              }}
              className={CONTROL_BUTTON}
              data-tone="sun"
            >
              {hasDroppedPin ? (
                <MapPinOff className="w-4 h-4" aria-hidden="true" />
              ) : (
                <MapPin className="w-4 h-4" aria-hidden="true" />
              )}
              {hasDroppedPin ? 'Remove pin' : isPinMode ? 'Tap the map' : 'Drop pin'}
            </button>

            {pinMessage && (
              <p
                role="status"
                className="absolute right-0 top-[calc(100%+8px)] w-[220px] px-3 py-2 rounded-lg bg-white border border-line shadow-[0_4px_12px_rgba(24,43,73,0.16)] text-[12px] font-medium text-[#835300]"
              >
                {pinMessage}
              </p>
            )}

            {/* Desktop: opens to the left of the Time button, level with the buttons.
                Phone: no room beside it, so it drops below. */}
            {isTimeOpen && (
              <div className="absolute max-sm:right-0 max-sm:top-[calc(100%+8px)] sm:right-full sm:mr-2 sm:top-0">
                {timePanel}
              </div>
            )}
          </div>,
          basemapControlEl
        )}
    </>
  );
};
