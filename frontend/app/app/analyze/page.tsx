import type { Metadata } from 'next';
import { LandingNav } from '@/components/landing/LandingNav';
import { Footer } from '@/components/landing/Footer';
import { AnalyzeContent } from '@/components/landing/AnalyzeContent';

export const metadata: Metadata = {
  title: 'Analyze — Mihna',
  description:
    'A workspace for cross-cohort analysis of the GCC labor market: salary bands, skill graphs, demand maps. In development.',
};

export default function AnalyzePage() {
  return (
    <>
      <LandingNav />
      <main id="main">
        <AnalyzeContent />
      </main>
      <Footer />
    </>
  );
}
