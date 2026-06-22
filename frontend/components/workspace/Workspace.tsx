'use client';

import { useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { usePathname } from 'next/navigation';
import { fetchDashboard, fetchDatasets, fetchModels, ModelOption } from '@/lib/api';
import { DumpInfo } from '@/lib/types';
import Sidebar from '@/components/Sidebar';
import Dashboard from '@/components/Dashboard';
import Chat from '@/components/Chat';
import { useLanguage } from '@/lib/i18n';
import { AppHeader } from './AppHeader';

type WorkspaceMode = 'dashboard' | 'chat';

export function Workspace({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const mode: WorkspaceMode = pathname.startsWith('/app/chat') ? 'chat' : 'dashboard';
  const [dumps, setDumps] = useState<DumpInfo[]>([]);
  const [timelines, setTimelines] = useState<string[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [models, setModels] = useState<ModelOption[]>([]);
  const [model, setModel] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const reduceMotion = useReducedMotion();
  const { dir } = useLanguage();

  useEffect(() => {
    if (!sidebarOpen) return;

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setSidebarOpen(false);
    }

    document.addEventListener('keydown', closeOnEscape);
    return () => document.removeEventListener('keydown', closeOnEscape);
  }, [sidebarOpen]);

  useEffect(() => {
    fetchDatasets()
      .then((datasets) => {
        const dumpIds = datasets.dumps.map((dump) => dump._dump_id);
        setDumps(datasets.dumps);
        setTimelines(datasets.timelines);
        setSelected(dumpIds);
        void fetchDashboard({ dumps: dumpIds }).catch(() => {});
      })
      .catch(() => setLoadError('Data scope is unavailable. Check the API connection and reload.'))
      .finally(() => setLoading(false));

    fetchModels()
      .then((modelData) => {
        setModels(modelData.models);
        setModel(modelData.default);
      })
      .catch(() => {});
  }, []);

  function toggleDump(id: string) {
    setSelected((current) => (
      current.includes(id) ? current.filter((value) => value !== id) : [...current, id]
    ));
  }

  function handleTimelineSelect(timeline: string) {
    setSelected(
      timeline === 'All'
        ? dumps.map((dump) => dump._dump_id)
        : dumps.filter((dump) => dump._timeline === timeline).map((dump) => dump._dump_id),
    );
  }

  function handleCountrySelect(country: string) {
    setSelected(
      country === 'All'
        ? dumps.map((dump) => dump._dump_id)
        : dumps.filter((dump) => dump._country === country).map((dump) => dump._dump_id),
    );
  }

  const dashboardScope = useMemo(() => {
    const selectedDumps = dumps.filter((dump) => selected.includes(dump._dump_id));
    const selectedTimelines = [...new Set(selectedDumps.map((dump) => dump._timeline))];
    const selectedCountries = [...new Set(selectedDumps.map((dump) => dump._country))];
    const allCountries = [...new Set(dumps.map((dump) => dump._country))].sort();
    const allCountryCounts: Record<string, number> = {};
    dumps.forEach((dump) => {
      allCountryCounts[dump._country] = (allCountryCounts[dump._country] ?? 0) + dump.count;
    });

    return {
      activeTimeline: selectedTimelines.length === 1 ? selectedTimelines[0] : 'All',
      activeCountry: selectedCountries.length === 1 ? selectedCountries[0] : 'All',
      allCountries,
      allCountryCounts,
    };
  }, [dumps, selected]);

  return (
    <div className="app-workspace" dir="ltr">
      <AppHeader
        scopeOpen={sidebarOpen}
        onOpenScope={() => setSidebarOpen((open) => !open)}
      />
      <div className="app-workspace__body">
        <AnimatePresence>
          {sidebarOpen && (
            <motion.div
              className="app-sidebar-layer"
              initial={reduceMotion ? false : { width: 0 }}
              animate={{ width: 320 }}
              exit={{ width: 0 }}
              transition={{
                duration: reduceMotion ? 0 : 0.26,
                ease: [0.22, 1, 0.36, 1],
              }}
            >
              <motion.div
                className="app-sidebar-layer__content"
                initial={reduceMotion ? false : { x: -16, opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                exit={{ x: -12, opacity: 0 }}
                transition={{
                  duration: reduceMotion ? 0 : 0.18,
                  ease: [0.2, 0, 0, 1],
                }}
              >
                <Sidebar
                  dumps={dumps}
                  timelines={timelines}
                  selected={selected}
                  model={model}
                  models={models}
                  isOpen
                  showModel={mode === 'chat'}
                  onToggle={toggleDump}
                  onSelectAll={() => setSelected(dumps.map((dump) => dump._dump_id))}
                  onClearAll={() => setSelected([])}
                  onModelChange={setModel}
                />
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

        <main id="main" className="app-workspace__main" dir={dir}>
          {loading ? (
            <WorkspaceLoading mode={mode} />
          ) : loadError ? (
            <div className="app-state" role="alert">
              <p className="app-state__title">Unable to load the workspace</p>
              <p>{loadError}</p>
            </div>
          ) : mode === 'dashboard' ? (
            <Dashboard
              selectedDumps={selected}
              allTimelines={timelines}
              activeTimeline={dashboardScope.activeTimeline}
              onTimelineSelect={handleTimelineSelect}
              allCountries={dashboardScope.allCountries}
              allCountryCounts={dashboardScope.allCountryCounts}
              activeCountry={dashboardScope.activeCountry}
              onCountrySelect={handleCountrySelect}
            />
          ) : (
            <Chat selectedDumps={selected} model={model} />
          )}
          {children}
        </main>
      </div>
    </div>
  );
}

function WorkspaceLoading({ mode }: { mode: WorkspaceMode }) {
  return (
    <div className="app-loading" aria-busy="true" aria-label={`Loading ${mode}`}>
      <div className="app-loading__line app-loading__line--short" />
      <div className="app-loading__line" />
      <div className="app-loading__grid">
        <div />
        <div />
        <div />
      </div>
    </div>
  );
}
