import type { Metadata } from "next";
import { Fraunces, Geist, Geist_Mono, Reem_Kufi, IBM_Plex_Sans_Arabic } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/lib/theme";
import { LanguageProvider } from "@/lib/i18n";

/* English display — variable serif with optical-size + softness axes.
   Variable axes require omitting `weight` (next/font treats the family
   as a variable font when `axes` is set). The wght axis remains
   accessible via fontVariationSettings in the components. */
const fraunces = Fraunces({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-fraunces",
  axes: ["opsz", "SOFT"],
});

const geistSans = Geist({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-geist-sans",
});

const geistMono = Geist_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-geist-mono",
});

/* Arabic display — geometric kufi, distinctive at large sizes. */
const reemKufi = Reem_Kufi({
  subsets: ["arabic", "latin"],
  display: "swap",
  variable: "--font-reem-kufi",
  weight: ["400", "500", "600", "700"],
});

/* Arabic body — Plex Sans Arabic, IBM's neutral humanist face. */
const plexArabic = IBM_Plex_Sans_Arabic({
  subsets: ["arabic", "latin"],
  display: "swap",
  variable: "--font-plex-arabic",
  weight: ["300", "400", "500", "600"],
});

export const metadata: Metadata = {
  title: "Mihna — AI-powered labor market intelligence",
  description:
    "Mihna explores GCC labor-market trends, skills, salaries, and workforce demand with AI-grounded analytics and a conversational assistant.",
  metadataBase: new URL("https://mihna.qa"),
  openGraph: {
    title: "Mihna — AI-powered labor market intelligence",
    description:
      "Explore GCC labor-market trends, skills, salaries, and workforce demand with AI-grounded analytics.",
    type: "website",
    locale: "en_QA",
    alternateLocale: "ar_QA",
  },
};

/* Inline init: applies stored theme + language before paint to prevent
   flash. Defaults: light theme, English. */
const initScript = `
(function () {
  try {
    var theme = localStorage.getItem('theme');
    if (theme !== 'light' && theme !== 'dark') theme = 'light';
    document.documentElement.setAttribute('data-theme', theme);

    var lang = localStorage.getItem('lang');
    if (lang !== 'ar' && lang !== 'en') lang = 'en';
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
  } catch (e) {}
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      dir="ltr"
      className={`${fraunces.variable} ${geistSans.variable} ${geistMono.variable} ${reemKufi.variable} ${plexArabic.variable} h-full`}
      data-theme="light"
      data-scroll-behavior="smooth"
      suppressHydrationWarning
    >
      <head>
        <link
          rel="icon"
          type="image/svg+xml"
          href="/brand/mihna-mark.svg"
        />
        <link
          rel="apple-touch-icon"
          type="image/png"
          sizes="180x180"
          href="/brand/mihna-apple-touch-icon.png"
        />
        <script dangerouslySetInnerHTML={{ __html: initScript }} />
      </head>
      <body className="h-full">
        <ThemeProvider>
          <LanguageProvider>{children}</LanguageProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
