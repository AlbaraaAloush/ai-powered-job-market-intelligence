"use client";

import { createContext, use, useEffect, useState, ReactNode } from "react";

export type Lang = "en" | "ar";

type Dict = Record<string, unknown>;

const dictionaries: Record<Lang, Dict> = {
  en: {
    nav: {
      brand: "Mihna",
      features: "Features",
      modules: "Modules",
      team: "Team",
      faq: "FAQ",
      cta: "Open dashboard",
      moduleDashboard: "Dashboard",
      moduleDashboardSub: "Filter postings by country, sector, and seniority",
      moduleChat: "Chat",
      moduleChatSub: "Ask the data in plain English or Arabic",
      soon: "Soon",
      menu: "Menu",
      close: "Close",
      light: "Light",
      dark: "Dark",
      switchToArabic: "العربية",
      switchToEnglish: "English",
      skipToContent: "Skip to content",
    },
    mihna: {
      heroEyebrow: "AI-powered labor market intelligence",
      heroTagPrefix: "Read the GCC job market through",
      heroTagSuffix: "",
      heroLead:
        "Mihna grounds AI analysis in live job postings from across the Gulf — built for analysts, researchers, and policymakers reading workforce data with care.",
      heroPrimary: "Open dashboard",
      heroSecondary: "How it works",

      featuresTitle: "Features",
      featLiveTitle: "Live dashboard",
      featLiveDesc:
        "Filter postings by country, sector, seniority, and time. Charts re-render the moment a filter lands.",
      featLiveCta: "Open dashboard",
      featChatTitle: "Conversational analysis",
      featChatDesc:
        "Ask in English or Arabic. Answers cite the underlying postings and respect the filters you set.",
      featChatCta: "Ask the data",
      featCoverageTitle: "Multi-country coverage",
      featCoverageDesc:
        "Qatar, the UAE, and Saudi Arabia today. Bahrain, Kuwait, and Oman on deck — all under a single schema.",
      featBenchTitle: "Snapshot benchmarking",
      featBenchDesc:
        "Compare any two months side-by-side. Caveats on disclosure rates surface alongside the numbers, not buried in footnotes.",
      featExportTitle: "Reproducible exports",
      featExportDesc:
        "Pull a chart, a filter, a dataset. The script that generated it is bundled with the export.",

      teamTitle: "Team",
      teamMember1Name: "Dr. Hamdy Mubarak",
      teamMember1Role: "Principal Software Engineer",
      teamMember2Name: "Abubakr Mohamed",
      teamMember2Role: "",
      teamMember3Name: "Albaraa Aloush",
      teamMember3Role: "",
      teamMember4Name: "Mohammad Faiz",
      teamMember4Role: "",
      teamMember5Name: "Yahya Taha",
      teamMember5Role: "",

      faqTitle: "Frequently asked questions",
      faq1Q: "Where does the data come from?",
      faq1A:
        "Job postings are continuously collected from Bayt.com and LinkedIn across Gulf countries. We treat raw snapshots as immutable inputs — every chart cites its source file, snapshot date, geography, and row count.",
      faq2Q: "What is Fanar?",
      faq2A:
        "Fanar is an Arabic-first large language model used to normalize and analyze postings. It extracts skills, sectors, salary bands, and trends without losing the Arabic-language signal that GCC postings carry.",
      faq3Q: "Can I ask the assistant questions in Arabic?",
      faq3A:
        "Yes. The conversational layer answers in either language and grounds every response in the same filters you set on the dashboard. There is no separate model per language.",
      faq4Q: "Which countries are covered today?",
      faq4A:
        "Qatar is the primary focus, with the UAE and Saudi Arabia available now. Bahrain, Kuwait, and Oman are on the roadmap, all under the same schema so cross-country comparisons stay honest.",
      faq5Q: "How fresh is the data?",
      faq5A:
        "Snapshots are pulled on a regular cadence. Where snapshot dates differ across countries, the dashboard surfaces that explicitly — month-over-month comparisons always state the snapshot dates being compared.",
      faq6Q: "Why is salary disclosure so partial?",
      faq6A:
        "Disclosure rates in GCC postings are low. Mihna flags low-confidence salary conclusions with a visible caveat rather than smoothing them away. We would rather show you the gap than fabricate a clean number.",

      footerTagline:
        "AI-grounded labor-market intelligence for Qatar and the wider Gulf.",
      footerContactTitle: "Contact",
      footerProductTitle: "Product",
      footerCompanyTitle: "About",
      footerLinkDashboard: "Dashboard",
      footerLinkChat: "Chat",
      footerLinkFeatures: "Features",
      footerLinkTeam: "Team",
      footerLinkFaq: "FAQ",
      footerLocation: "Doha, Qatar",
      footerEmail: "hello@mihna.qa",
      footerPhone: "+974. 445. 47781",
      footerRights: "© 2026 Mihna. All rights reserved.",
      footerInstitution: "A QCRI labor-market research project.",
    },
    /* Legacy /app dashboard keys — referenced by components/Dashboard.tsx,
       components/Chat.tsx, components/Sidebar.tsx, app/app/page.tsx. */
    app: {
      title: "Mihna",
      dashboard: "Dashboard",
      chat: "Chat",
      home: "Home",
    },
  },
  ar: {
    nav: {
      brand: "مِهنَة",
      features: "الإمكانات",
      modules: "الوحدات",
      team: "الفريق",
      faq: "الأسئلة",
      cta: "افتح لوحة التحكم",
      moduleDashboard: "لوحة التحكم",
      moduleDashboardSub: "استعرض الإعلانات حسب الدولة والقطاع والمستوى",
      moduleChat: "المحادثة",
      moduleChatSub: "اسأل البيانات بالعربية أو الإنجليزية",
      soon: "قريباً",
      menu: "القائمة",
      close: "إغلاق",
      light: "فاتح",
      dark: "داكن",
      switchToArabic: "العربية",
      switchToEnglish: "English",
      skipToContent: "تخطَّ إلى المحتوى",
    },
    mihna: {
      heroEyebrow: "ذكاء اصطناعي لسوق العمل",
      heroTagPrefix: "اقرأ سوق العمل الخليجي عبر",
      heroTagSuffix: "",
      heroLead:
        "تستند مِهنَة إلى إعلانات وظائف حقيقية من الخليج، مبنيّة للمحلّلين والباحثين وصنّاع السياسات الذين يقرأون بيانات القوى العاملة بدقّة.",
      heroPrimary: "افتح لوحة التحكم",
      heroSecondary: "كيف تعمل",

      featuresTitle: "الإمكانات",
      featLiveTitle: "لوحة تحكم حيّة",
      featLiveDesc:
        "فلترة الإعلانات حسب الدولة والقطاع والمستوى الوظيفي والزمن. تتحدّث الرسوم البيانية لحظة تثبيت أي فلتر.",
      featLiveCta: "افتح لوحة التحكم",
      featChatTitle: "تحليل بالمحادثة",
      featChatDesc:
        "اسأل بالعربية أو الإنجليزية. تستشهد الإجابات بالإعلانات الفعلية وتحترم الفلاتر التي اخترتها.",
      featChatCta: "اسأل البيانات",
      featCoverageTitle: "تغطية متعدّدة الدول",
      featCoverageDesc:
        "قطر والإمارات والسعودية اليوم. البحرين والكويت وعُمان قيد الإضافة، تحت بنية موحّدة للمقارنة.",
      featBenchTitle: "مقارنة لقطات زمنيّة",
      featBenchDesc:
        "قارن أي شهرين جنباً إلى جنب. تظهر تحفّظات نسب الإفصاح إلى جانب الأرقام، لا في الهامش.",
      featExportTitle: "تصدير قابل للتكرار",
      featExportDesc:
        "صدِّر رسماً أو فلتراً أو مجموعة بيانات. يصاحب التصدير السكربت الذي أنتجه.",

      teamTitle: "الفريق",
      teamMember1Name: "د. حمدي مبارك",
      teamMember1Role: "مهندس برمجيّات أوّل",
      teamMember2Name: "أبوبكر محمد",
      teamMember2Role: "",
      teamMember3Name: "البراء علوش",
      teamMember3Role: "",
      teamMember4Name: "محمّد فايز",
      teamMember4Role: "",
      teamMember5Name: "يحيى طه",
      teamMember5Role: "",

      faqTitle: "الأسئلة الشائعة",
      faq1Q: "من أين تأتي البيانات؟",
      faq1A:
        "تُجمع إعلانات الوظائف باستمرار من Bayt و LinkedIn في دول الخليج. نتعامل مع اللقطات الخام كمدخلات لا تُعدَّل، ويذكر كل رسم مصدره وتاريخ اللقطة والجغرافيا وعدد الصفوف.",
      faq2Q: "ما هو Fanar؟",
      faq2A:
        "Fanar نموذج لغوي عربي أوّل يُستخدم لتطبيع الإعلانات وتحليلها، يستخرج المهارات والقطاعات وفئات الرواتب والاتجاهات دون فقد الإشارة العربيّة في الإعلانات الخليجيّة.",
      faq3Q: "هل يمكنني سؤال المساعد بالعربيّة؟",
      faq3A:
        "نعم. تجيب طبقة المحادثة بأيٍّ من اللغتين، وتلتزم بالفلاتر نفسها التي اخترتها على لوحة التحكم. لا نموذج منفصل لكل لغة.",
      faq4Q: "ما الدول المُغطّاة الآن؟",
      faq4A:
        "قطر هي محور التركيز، مع الإمارات والسعودية المتاحتين الآن. البحرين والكويت وعُمان على خارطة الطريق، ضمن نفس البنية لتظلّ المقارنات أمينة.",
      faq5Q: "ما مدى حداثة البيانات؟",
      faq5A:
        "تُسحب اللقطات بإيقاع منتظم. حين تختلف تواريخ اللقطات بين الدول، تُظهر اللوحة ذلك صراحةً، وتُذكَر تواريخ المقارنة دائماً.",
      faq6Q: "لماذا الإفصاح عن الراتب جزئيّ؟",
      faq6A:
        "نسب الإفصاح في الإعلانات الخليجيّة منخفضة. تُشير مِهنَة بوضوح إلى استنتاجات الراتب منخفضة الثقة بدل تنعيمها. نُريك الفجوة بدل اختلاق رقم نظيف.",

      footerTagline: "ذكاء اصطناعي لقراءة سوق العمل في قطر والخليج.",
      footerContactTitle: "تواصل",
      footerProductTitle: "المنتج",
      footerCompanyTitle: "عنّا",
      footerLinkDashboard: "لوحة التحكم",
      footerLinkChat: "المحادثة",
      footerLinkFeatures: "الإمكانات",
      footerLinkTeam: "الفريق",
      footerLinkFaq: "الأسئلة",
      footerLocation: "الدوحة، قطر",
      footerEmail: "hello@mihna.qa",
      footerPhone: "+974. 445. 47781",
      footerRights: "© 2026 مِهنَة. جميع الحقوق محفوظة.",
      footerInstitution: "مشروع بحثي ضمن معهد قطر لبحوث الحوسبة.",
    },
    app: {
      title: "مِهنَة",
      dashboard: "لوحة التحكم",
      chat: "المحادثة",
      home: "الرئيسية",
    },
  },
};

interface LanguageContextValue {
  lang: Lang;
  dir: "ltr" | "rtl";
  toggleLang: () => void;
  t: (path: string) => string;
}

const LanguageContext = createContext<LanguageContextValue>({
  lang: "en",
  dir: "ltr",
  toggleLang: () => {},
  t: (path: string) => path,
});

function lookup(dict: Dict, path: string): string {
  const value = path
    .split(".")
    .reduce<unknown>(
      (acc, key) => (acc == null ? acc : (acc as Dict)[key]),
      dict,
    );
  return typeof value === "string" ? value : path;
}

/* SSR + initial client render both default to 'en' so hydration
   matches; the inline script in layout.tsx has already set
   html[lang] + html[dir] correctly so the layout itself never flashes.
   After mount, the effect aligns React state with the stored value.
   Brief text-content sync flash is acceptable; the alternative would
   require cookies-based SSR. */
function applyLang(next: Lang) {
  document.documentElement.lang = next;
  document.documentElement.dir = next === "ar" ? "rtl" : "ltr";
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>("en");

  useEffect(() => {
    const stored = window.localStorage.getItem("lang") as Lang | null;
    const initial: Lang = stored === "ar" || stored === "en" ? stored : "en";
    applyLang(initial);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLang(initial);
  }, []);

  function toggleLang() {
    setLang((prev) => {
      const next: Lang = prev === "en" ? "ar" : "en";
      applyLang(next);
      try {
        window.localStorage.setItem("lang", next);
      } catch {
        /* private browsing / quota — fail silently. */
      }
      return next;
    });
  }

  const dir: "ltr" | "rtl" = lang === "ar" ? "rtl" : "ltr";
  const t = (path: string) => lookup(dictionaries[lang], path);

  return (
    <LanguageContext.Provider value={{ lang, dir, toggleLang, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  return use(LanguageContext);
}
