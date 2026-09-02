import { LandingNav } from '@/components/landing/LandingNav';
import { Hero } from '@/components/landing/Hero';
import { Features } from '@/components/landing/Features';
import { Team } from '@/components/landing/Team';
import { FAQ } from '@/components/landing/FAQ';
import { Footer } from '@/components/landing/Footer';

export default function HomePage() {
  return (
    <>
      <LandingNav />
      <main id="main">
        <Hero />
        <Features />
        <Team />
        <FAQ />
      </main>
      <Footer />
    </>
  );
}
