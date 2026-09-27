import type { LayerSpecification } from 'maplibre-gl'

// Holder codes for the layer strips.
export const LAYER_CODE: Record<string, string> = {
  earthquakes: 'EQK',
  disasters: 'DIS',
  fires: 'FIR',
  aircraft: 'ADS',
  ships: 'AIS',
  iss: 'ISS',
  cables: 'CAB',
  landings: 'LND',
  news: 'NEW',
  incidents: 'INC',
  daynight: 'SUN',
}

// Swatch colours shown in the layer panel; kept in step with the paint below.
export const SWATCH: Record<string, string> = {
  earthquakes: '#f06b5b',
  disasters: '#f2b33d',
  fires: '#ff8a3d',
  aircraft: '#6fb3e0',
  ships: '#5fc79a',
  iss: '#ffffff',
  cables: '#7c93a6',
  landings: '#b8c9d1',
  news: '#9aa9ff',
  incidents: '#e0527a',
  daynight: '#a3a3a3',
}

type Spec = Omit<LayerSpecification, 'id' | 'source'> & { idSuffix?: string }

export const LAYER_STYLE: Record<string, Spec[]> = {
  daynight: [{ type: 'fill', paint: { 'fill-color': '#02070a', 'fill-opacity': 0.55 } }],
  cables: [
    {
      type: 'line',
      paint: { 'line-color': ['coalesce', ['get', 'color'], '#7c93a6'], 'line-width': 1.2, 'line-opacity': 0.55 },
    },
  ],
  landings: [
    {
      type: 'circle',
      minzoom: 2,
      paint: { 'circle-radius': 2.5, 'circle-color': '#b8c9d1', 'circle-opacity': 0.8 },
    },
  ],
  fires: [
    {
      type: 'circle',
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['get', 'frp_mw'], 0, 1.5, 50, 3, 500, 6],
        'circle-color': '#ff8a3d',
        'circle-opacity': 0.75,
      },
    },
  ],
  earthquakes: [
    {
      type: 'circle',
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['coalesce', ['get', 'mag'], 0], 0, 2, 4, 6, 7, 18],
        'circle-color': '#f06b5b',
        'circle-opacity': 0.35,
        'circle-stroke-color': '#f06b5b',
        'circle-stroke-width': 1.2,
      },
    },
  ],
  disasters: [
    {
      type: 'circle',
      paint: {
        'circle-radius': 7,
        'circle-color': [
          'match',
          ['get', 'alertlevel'],
          'Red',
          '#f06b5b',
          'Orange',
          '#f2b33d',
          '#5fc79a',
        ],
        'circle-opacity': 0.25,
        'circle-stroke-width': 2,
        'circle-stroke-color': [
          'match',
          ['get', 'alertlevel'],
          'Red',
          '#f06b5b',
          'Orange',
          '#f2b33d',
          '#5fc79a',
        ],
      },
    },
  ],
  news: [
    {
      type: 'circle',
      paint: { 'circle-radius': 3.5, 'circle-color': '#9aa9ff', 'circle-opacity': 0.7 },
    },
  ],
  incidents: [
    {
      type: 'circle',
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['get', 'mentions'], 1, 4, 20, 9],
        'circle-color': '#e0527a',
        'circle-opacity': 0.4,
        'circle-stroke-color': '#e0527a',
        'circle-stroke-width': 1,
      },
    },
  ],
  aircraft: [
    {
      type: 'symbol',
      layout: {
        'icon-image': 'arrow',
        'icon-size': 0.55,
        'icon-rotate': ['coalesce', ['get', 'heading'], 0],
        'icon-rotation-alignment': 'map',
        'icon-allow-overlap': true,
      },
      paint: { 'icon-color': '#6fb3e0', 'icon-opacity': ['case', ['get', 'on_ground'], 0.35, 0.9] },
    },
  ],
  ships: [
    {
      type: 'symbol',
      layout: {
        'icon-image': 'arrow',
        'icon-size': 0.45,
        'icon-rotate': ['coalesce', ['get', 'cog'], 0],
        'icon-rotation-alignment': 'map',
        'icon-allow-overlap': true,
      },
      paint: { 'icon-color': '#5fc79a', 'icon-opacity': 0.85 },
    },
  ],
  iss: [
    {
      type: 'circle',
      paint: { 'circle-radius': 7, 'circle-color': '#ffffff', 'circle-stroke-color': '#f2b33d', 'circle-stroke-width': 3 },
    },
    {
      idSuffix: 'label',
      type: 'symbol',
      layout: { 'text-field': 'ISS', 'text-offset': [0, 1.4], 'text-size': 12, 'text-font': ['Open Sans Bold'] },
      paint: { 'text-color': '#ffffff', 'text-halo-color': '#0f1b22', 'text-halo-width': 1.5 },
    },
  ],
}

/** An SDF arrow for aircraft/vessels, tinted per layer via icon-color. */
export function arrowImage(size = 32) {
  const c = document.createElement('canvas')
  c.width = c.height = size
  const ctx = c.getContext('2d')!
  ctx.fillStyle = '#fff'
  ctx.beginPath()
  ctx.moveTo(size / 2, 2)
  ctx.lineTo(size - 6, size - 4)
  ctx.lineTo(size / 2, size - 10)
  ctx.lineTo(6, size - 4)
  ctx.closePath()
  ctx.fill()
  return ctx.getImageData(0, 0, size, size)
}
