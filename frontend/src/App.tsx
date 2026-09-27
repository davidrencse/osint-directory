import { FileSearch, Globe2, Library, Radar, SlidersHorizontal } from 'lucide-react'
import { lazy, Suspense } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import ReconPage from './pages/ReconPage'

// MapLibre is heavy; only the pages that draw maps pull it in.
const MapPage = lazy(() => import('./pages/MapPage'))
const MetadataPage = lazy(() => import('./pages/MetadataPage'))
const ToolsPage = lazy(() => import('./pages/ToolsPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))

const NAV = [
  { to: '/recon', label: 'Recon', short: 'Recon', icon: Radar },
  { to: '/map', label: 'World map', short: 'Map', icon: Globe2 },
  { to: '/metadata', label: 'File metadata', short: 'Files', icon: FileSearch },
  { to: '/tools', label: 'Tool library', short: 'Tools', icon: Library },
  { to: '/settings', label: 'Settings', short: 'Settings', icon: SlidersHorizontal },
]

function Mark() {
  return (
    <svg viewBox="0 0 32 32" className="size-9 shrink-0" aria-hidden>
      <circle cx="16" cy="16" r="14" fill="#050505" stroke="var(--color-rail)" />
      <circle cx="16" cy="16" r="9" fill="none" stroke="#1f1f1f" strokeDasharray="2 2" />
      <path d="M16 16 L16 2 A14 14 0 0 1 27 7.5 Z" fill="var(--color-scope)" opacity="0.28" />
      <path d="M16 16 L27 7.5" stroke="var(--color-scope)" strokeWidth="1.5" />
      <rect x="19.5" y="19" width="3.5" height="3.5" fill="var(--color-h-dns)" />
      <rect x="8" y="11" width="3.5" height="3.5" fill="var(--color-h-web)" />
    </svg>
  )
}

export default function App() {
  return (
    <div className="flex h-full flex-col md:flex-row">
      <nav
        aria-label="Main"
        className="rail-bg order-last flex shrink-0 border-t md:order-first md:w-52 md:flex-col md:border-t-0 md:border-r"
      >
        <div className="hidden items-center gap-3 px-4 pt-5 pb-7 md:flex">
          <Mark />
          <div>
            <div className="page-title text-lg leading-none font-semibold">Sounding</div>
            <div className="mt-1 text-xs text-console-2">Infrastructure recon</div>
          </div>
        </div>
        <ul className="flex w-full justify-around md:flex-col md:gap-1 md:px-2.5">
          {NAV.map(({ to, label, short, icon: Icon }) => (
            <li key={to}>
              <NavLink
                to={to}
                className={({ isActive }) =>
                  `flex flex-col items-center gap-1 px-3 py-2 text-xs transition-colors md:flex-row md:gap-3 md:rounded-md md:px-3 md:py-2 md:text-sm ${
                    isActive ? 'text-console md:nav-active [&_svg]:text-scope' : 'text-console-2 hover:text-console md:hover:bg-white/[0.04]'
                  }`
                }
              >
                <Icon className="size-5 md:size-[18px]" strokeWidth={1.75} aria-hidden />
                <span className="md:hidden">{short}</span>
                <span className="hidden md:inline">{label}</span>
              </NavLink>
            </li>
          ))}
        </ul>
        <p className="mt-auto hidden px-4 pb-5 text-xs leading-relaxed text-console-3 md:block">
          Runs on your machine. API keys stay in the backend and every sweep is logged.
        </p>
      </nav>
      <main className="min-h-0 min-w-0 flex-1 overflow-y-auto">
        <Suspense fallback={<p className="p-8 text-console-2">Loading…</p>}>
          <Routes>
            <Route path="/" element={<Navigate to="/recon" replace />} />
            <Route path="/recon" element={<ReconPage />} />
            <Route path="/map" element={<MapPage />} />
            <Route path="/metadata" element={<MetadataPage />} />
            <Route path="/tools" element={<ToolsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/recon" replace />} />
          </Routes>
        </Suspense>
      </main>
    </div>
  )
}
