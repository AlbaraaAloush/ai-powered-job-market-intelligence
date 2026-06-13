import type { Metadata } from 'next';
import { AnalyzePlaceholder } from '@/components/workspace/AnalyzePlaceholder';
import { AppHeader } from '@/components/workspace/AppHeader';

export const metadata: Metadata = {
  title: 'Analyze | Mihna',
  description:
    'A workspace for cross-cohort analysis of the GCC labor market: salary bands, skill graphs, demand maps. In development.',
};

export default function AnalyzePage() {
  return (
    <div className="app-workspace">
      <AppHeader />
      <main id="main" className="app-analyze">
        <AnalyzePlaceholder />
      </main>
    </div>
  );
}
