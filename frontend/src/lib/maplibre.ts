// MapLibre v6 resolves its worker relative to its own module URL, which breaks once Vite
// pre-bundles or builds it. Let Vite bundle the worker and hand MapLibre the resulting URL.
import * as maplibregl from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'

maplibregl.setWorkerUrl(workerUrl)

export { maplibregl }
