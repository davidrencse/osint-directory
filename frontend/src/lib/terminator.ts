// Night-side polygon for the day/night terminator (after Leaflet.Terminator, MIT).
const R2D = 180 / Math.PI
const D2R = Math.PI / 180

function julian(date: Date) {
  return date.getTime() / 86400000 + 2440587.5
}

function gmst(jd: number) {
  const d = jd - 2451545.0
  return (18.697374558 + 24.06570982441908 * d) % 24
}

function sunEcliptic(jd: number) {
  const n = jd - 2451545.0
  const L = (280.46 + 0.9856474 * n) % 360
  const g = ((357.528 + 0.9856003 * n) % 360) * D2R
  return L + 1.915 * Math.sin(g) + 0.02 * Math.sin(2 * g)
}

function obliquity(jd: number) {
  const T = (jd - 2451545.0) / 36525
  return (
    23.43929111 -
    T * (46.836769 / 3600 - T * (0.0001831 / 3600 + T * (0.0020034 / 3600 - T * (0.576e-6 / 3600 - (T * 4.34e-8) / 3600))))
  )
}

export function nightPolygon(date = new Date()): GeoJSON.Feature<GeoJSON.Polygon> {
  const jd = julian(date)
  const gst = gmst(jd)
  const lambda = sunEcliptic(jd)
  const eps = obliquity(jd)
  let alpha = Math.atan(Math.cos(eps * D2R) * Math.tan(lambda * D2R)) * R2D
  const delta = Math.asin(Math.sin(eps * D2R) * Math.sin(lambda * D2R)) * R2D
  alpha += Math.floor(lambda / 90) * 90 - Math.floor(alpha / 90) * 90

  const ring: [number, number][] = []
  for (let i = 0; i <= 720; i++) {
    const lng = -180 + i / 2
    const ha = (gst + lng / 15) * 15 - alpha
    const lat = Math.atan(-Math.cos(ha * D2R) / Math.tan(delta * D2R)) * R2D
    ring.push([lng, lat])
  }
  const pole = delta < 0 ? 90 : -90
  ring.push([180, pole], [-180, pole], ring[0])
  return {
    type: 'Feature',
    properties: {},
    geometry: { type: 'Polygon', coordinates: [ring] },
  }
}
