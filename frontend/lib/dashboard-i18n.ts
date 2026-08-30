'use client';

import { useMemo } from 'react';
import arMessages from '@/locales/dashboard.ar.json';
import enMessages from '@/locales/dashboard.en.json';
import { Lang, useLanguage } from '@/lib/i18n';

type Messages = typeof enMessages;
export type DashboardMessageKey = keyof Messages;
export type DashboardValueDimension =
  | 'country' | 'timeline' | 'sector' | 'career' | 'employment' | 'education'
  | 'skill' | 'title' | 'company' | 'experience' | 'companySize' | 'language'
  | 'location' | 'gender' | 'salaryBracket' | 'bilingual';

const MESSAGE_SETS: Record<Lang, Messages> = {
  en: enMessages,
  ar: arMessages,
};

const ARABIC_LABELS: Partial<Record<DashboardValueDimension, Record<string, string>>> = {
  country: {
    All: 'الكل', Qatar: 'قطر', UAE: 'الإمارات العربية المتحدة',
    'Saudi Arabia': 'المملكة العربية السعودية', Bahrain: 'البحرين',
    Kuwait: 'الكويت', Oman: 'عُمان', Unknown: 'غير معروف',
  },
  sector: {
    Engineering: 'الهندسة', Construction: 'الإنشاءات', Technology: 'التقنية', Sales: 'المبيعات',
    Hospitality: 'الضيافة', Healthcare: 'الرعاية الصحية', 'Business Support': 'دعم الأعمال',
    Education: 'التعليم', Finance: 'التمويل', 'Oil & Gas': 'النفط والغاز', Marketing: 'التسويق',
    Manufacturing: 'التصنيع', Consulting: 'الاستشارات', 'Human Resources': 'الموارد البشرية',
    Logistics: 'الخدمات اللوجستية', Accounting: 'المحاسبة', Beauty: 'التجميل',
    'Real Estate': 'العقارات', 'Customer Service': 'خدمة العملاء',
    'Commercial Support': 'الدعم التجاري', Legal: 'الشؤون القانونية', Design: 'التصميم',
    Services: 'الخدمات', Management: 'الإدارة', Retail: 'تجارة التجزئة', Procurement: 'المشتريات',
    'Business Development': 'تطوير الأعمال', Energy: 'الطاقة', Banking: 'الخدمات المصرفية',
    Operations: 'العمليات', Automotive: 'السيارات', 'Other Business Support Services': 'خدمات دعم أعمال أخرى',
    'Financial Services': 'الخدمات المالية', Aerospace: 'الطيران والفضاء',
    'Facilities Management': 'إدارة المرافق', Aviation: 'الطيران', Transportation: 'النقل',
    Media: 'الإعلام', 'Food & Beverage': 'الأغذية والمشروبات', Architecture: 'العمارة',
    Technical: 'الخدمات الفنية', 'IT & Technology': 'تقنية المعلومات والتقنية',
    'Information Technology Services': 'خدمات تقنية المعلومات',
    'Retail and Wholesale': 'تجارة التجزئة والجملة', 'Food Production': 'إنتاج الأغذية',
  },
  career: {
    'Mid-Level': 'متوسط الخبرة', Senior: 'خبير', 'Entry-Level': 'مبتدئ', Manager: 'مدير',
    Executive: 'إدارة تنفيذية', Director: 'مدير إدارة', Leadership: 'قيادي',
    'Post-Doctoral': 'باحث ما بعد الدكتوراه', Postdoctoral: 'باحث ما بعد الدكتوراه',
    'Post-Doc': 'باحث ما بعد الدكتوراه', Postdoc: 'باحث ما بعد الدكتوراه', Principal: 'رئيسي',
    Experienced: 'ذو خبرة', 'Assistant Professor': 'أستاذ مساعد',
    'Head of Primary School': 'مدير مدرسة ابتدائية', 'Deputy Head': 'نائب المدير', Expert: 'خبير',
    'Expert-Level': 'مستوى خبير', Specialist: 'اختصاصي', 'Lead Specialist': 'اختصاصي أول', Assistant: 'مساعد',
  },
  employment: {
    'Full-Time': 'دوام كامل', Contract: 'عقد', Internship: 'تدريب', Remote: 'عن بُعد',
    'Part-Time': 'دوام جزئي', Freelance: 'عمل حر', Temporary: 'مؤقت',
  },
  companySize: {
    '1–50': 'من ١ إلى ٥٠ موظفاً', '51–200': 'من ٥١ إلى ٢٠٠ موظف',
    '201–500': 'من ٢٠١ إلى ٥٠٠ موظف', '501–1,000': 'من ٥٠١ إلى ١٬٠٠٠ موظف',
    '1,001–5,000': 'من ١٬٠٠١ إلى ٥٬٠٠٠ موظف', '5,001–10,000': 'من ٥٬٠٠١ إلى ١٠٬٠٠٠ موظف',
    '10,001–50,000': 'من ١٠٬٠٠١ إلى ٥٠٬٠٠٠ موظف', '50,000+': 'أكثر من ٥٠٬٠٠٠ موظف',
  },
  salaryBracket: {
    '<$500': 'أقل من ٥٠٠ دولار', '$500-1K': 'من ٥٠٠ إلى ١٬٠٠٠ دولار',
    '$1K-1.5K': 'من ١٬٠٠٠ إلى ١٬٥٠٠ دولار', '$1.5K-2K': 'من ١٬٥٠٠ إلى ٢٬٠٠٠ دولار',
    '$2K-3K': 'من ٢٬٠٠٠ إلى ٣٬٠٠٠ دولار', '$3K-5K': 'من ٣٬٠٠٠ إلى ٥٬٠٠٠ دولار',
    '$5K-7.5K': 'من ٥٬٠٠٠ إلى ٧٬٥٠٠ دولار', '$7.5K-10K': 'من ٧٬٥٠٠ إلى ١٠٬٠٠٠ دولار',
    '$10K-15K': 'من ١٠٬٠٠٠ إلى ١٥٬٠٠٠ دولار', '$15K+': 'أكثر من ١٥٬٠٠٠ دولار',
  },
  education: {
    Bachelor: 'بكالوريوس', "Bachelor's Degree": 'بكالوريوس', "Bachelor's degree": 'بكالوريوس',
    'High School': 'الثانوية العامة', 'High School Diploma': 'شهادة الثانوية العامة',
    'High school diploma or equivalent': 'الثانوية العامة أو ما يعادلها', Diploma: 'دبلوم',
    'Technical diploma': 'دبلوم تقني', 'Certification / diploma': 'شهادة مهنية أو دبلوم',
    Master: 'ماجستير', PhD: 'دكتوراه', Degree: 'شهادة جامعية', 'University Degree': 'شهادة جامعية',
    'Medical degree': 'شهادة في الطب', 'Medical Degree': 'شهادة في الطب',
    "Bachelor's degree / higher diploma": 'بكالوريوس أو دبلوم عالٍ',
    'Bachelor or Master': 'بكالوريوس أو ماجستير', 'Bachelor/Diploma': 'بكالوريوس أو دبلوم',
    'Degree or Diploma': 'شهادة جامعية أو دبلوم',
    'Technical, Trade, or Vocational School Degree': 'شهادة تقنية أو مهنية',
  },
  gender: {
    Any: 'لا تفضيل', Female: 'إناث', Male: 'ذكور',
    'Saudi Nationals Preferred': 'الأولوية للسعوديين', 'UAE Nationals Only': 'للمواطنين الإماراتيين فقط',
  },
  skill: {
    communication: 'التواصل', 'communication skills': 'مهارات التواصل',
    'project management': 'إدارة المشاريع', leadership: 'القيادة', 'problem-solving': 'حل المشكلات',
    'problem solving': 'حل المشكلات', 'analytical skills': 'المهارات التحليلية',
    'customer service': 'خدمة العملاء', 'attention to detail': 'الاهتمام بالتفاصيل',
    negotiation: 'التفاوض', 'stakeholder management': 'إدارة أصحاب المصلحة',
    'organizational skills': 'المهارات التنظيمية', 'risk management': 'إدارة المخاطر',
    'team leadership': 'قيادة الفرق', 'data analysis': 'تحليل البيانات', teamwork: 'العمل الجماعي',
    'team collaboration': 'التعاون ضمن الفريق', compliance: 'الامتثال', 'time management': 'إدارة الوقت',
    'interpersonal skills': 'مهارات التعامل مع الآخرين', troubleshooting: 'استكشاف الأعطال وإصلاحها',
    'quality assurance': 'ضمان الجودة', collaboration: 'التعاون', 'team management': 'إدارة الفرق',
    sales: 'المبيعات', reporting: 'إعداد التقارير', 'quality control': 'مراقبة الجودة',
    'market analysis': 'تحليل السوق', 'client relationship management': 'إدارة علاقات العملاء',
    documentation: 'التوثيق',
  },
  title: {
    'Nail Technician': 'فني أظافر', Accountant: 'محاسب', 'Sales Executive': 'تنفيذي مبيعات',
    'Project Manager': 'مدير مشروع', 'Massage Therapist': 'معالج تدليك',
    'Sales Representative': 'مندوب مبيعات', 'Business Development Manager': 'مدير تطوير أعمال',
    'Hair Stylist': 'مصفف شعر', 'Sales Manager': 'مدير مبيعات', 'Planning Engineer': 'مهندس تخطيط',
    'Electrical Engineer': 'مهندس كهرباء', 'Graphic Designer': 'مصمم جرافيك', Receptionist: 'موظف استقبال',
    'Document Controller': 'مراقب وثائق', 'Senior Electrical Engineer': 'مهندس كهرباء أول',
    'Senior Planning Engineer': 'مهندس تخطيط أول', 'Civil Engineer': 'مهندس مدني',
    'Executive Secretary': 'سكرتير تنفيذي', 'Real Estate Agent': 'وسيط عقاري',
    'Marketing Manager': 'مدير تسويق', 'Senior Accountant': 'محاسب أول', Electrician: 'كهربائي',
    'Sales Engineer': 'مهندس مبيعات', 'Marketing Specialist': 'اختصاصي تسويق',
    'Project Engineer': 'مهندس مشروع', 'Account Manager': 'مدير حسابات',
    'Mechanical Engineer': 'مهندس ميكانيكي', 'Project Coordinator': 'منسق مشروع',
    'Beauty Therapist': 'اختصاصي تجميل', 'Procurement Officer': 'مسؤول مشتريات',
  },
  location: {
    Qatar: 'قطر', Doha: 'الدوحة', Dubai: 'دبي', Riyadh: 'الرياض', 'Abu Dhabi': 'أبوظبي',
    'Saudi Arabia': 'المملكة العربية السعودية', UAE: 'الإمارات العربية المتحدة', Jeddah: 'جدة',
    Dammam: 'الدمام', Sharjah: 'الشارقة', 'Al Ain': 'العين', Khobar: 'الخبر', Qatif: 'القطيف',
    'Ras Al Khaimah': 'رأس الخيمة', 'Eastern Province': 'المنطقة الشرقية', Jubail: 'الجبيل',
    Ajman: 'عجمان', Mecca: 'مكة المكرمة', Medina: 'المدينة المنورة', 'Ras Laffan': 'رأس لفان',
    Dhahran: 'الظهران', Lusail: 'لوسيل', Abha: 'أبها', Fujairah: 'الفجيرة', Basra: 'البصرة',
    Unknown: 'غير معروف',
  },
  bilingual: {
    both: 'باللغتين العربية والإنجليزية', en_only: 'بالإنجليزية فقط', ar_only: 'بالعربية فقط',
  },
};

const ARABIC_MONTHS: Record<string, string> = {
  Jan: 'يناير', Feb: 'فبراير', Mar: 'مارس', Apr: 'أبريل', May: 'مايو', Jun: 'يونيو',
  Jul: 'يوليو', Aug: 'أغسطس', Sep: 'سبتمبر', Oct: 'أكتوبر', Nov: 'نوفمبر', Dec: 'ديسمبر',
};

const FORMATTERS = {
  en: {
    number: new Intl.NumberFormat('en-QA'),
    year: new Intl.NumberFormat('en-QA', { useGrouping: false }),
    compact: new Intl.NumberFormat('en-QA', { notation: 'compact', maximumFractionDigits: 1 }),
    currency: new Intl.NumberFormat('en-QA', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }),
    percent0: new Intl.NumberFormat('en-QA', { style: 'percent', maximumFractionDigits: 0 }),
    percent1: new Intl.NumberFormat('en-QA', { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 1 }),
  },
  ar: {
    number: new Intl.NumberFormat('ar-QA'),
    year: new Intl.NumberFormat('ar-QA', { useGrouping: false }),
    compact: new Intl.NumberFormat('ar-QA', { notation: 'compact', maximumFractionDigits: 1 }),
    currency: new Intl.NumberFormat('ar-QA', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }),
    percent0: new Intl.NumberFormat('ar-QA', { style: 'percent', maximumFractionDigits: 0 }),
    percent1: new Intl.NumberFormat('ar-QA', { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 1 }),
  },
} satisfies Record<Lang, Record<string, Intl.NumberFormat>>;

function interpolate(template: string, values?: Record<string, string | number>) {
  if (!values) return template;
  return template.replace(/\{(\w+)\}/g, (_, key: string) => String(values[key] ?? `{${key}}`));
}

function translateTimeline(value: string, number: (value: number) => string) {
  const match = /^([A-Z][a-z]{2})\s+(\d{4})$/.exec(value);
  if (!match) return value;
  return `${ARABIC_MONTHS[match[1]] ?? match[1]} ${number(Number(match[2]))}`;
}

function translateExperience(value: string, number: (value: number) => string) {
  if (value === 'No experience required') return 'لا تُشترط خبرة';
  let match = /^Minimum\s+(\d+)\s+years?$/i.exec(value);
  if (match) return `${number(Number(match[1]))} سنوات على الأقل`;
  match = /^(\d+)\+\s+years?$/i.exec(value);
  if (match) return `${number(Number(match[1]))} سنوات فأكثر`;
  match = /^(\d+)\s*[-–]\s*(\d+)\s+years?$/i.exec(value);
  if (match) return `من ${number(Number(match[1]))} إلى ${number(Number(match[2]))} سنوات`;
  match = /^(\d+)\s+years?$/i.exec(value);
  if (match) return `${number(Number(match[1]))} سنوات`;
  return value;
}

function translateLanguage(value: string) {
  const lower = value.toLocaleLowerCase('en');
  const hasArabic = lower.includes('arabic');
  const hasEnglish = lower.includes('english');
  const required = /must|mandatory|required/.test(lower);
  const preferred = /plus|advantage|preferred/.test(lower);
  if (hasArabic && hasEnglish) {
    if (required) return 'إجادة العربية والإنجليزية مطلوبة';
    if (preferred) return 'إجادة الإنجليزية، والعربية ميزة إضافية';
    return 'إجادة العربية والإنجليزية';
  }
  if (hasArabic) return required ? 'إجادة العربية مطلوبة' : preferred ? 'إجادة العربية ميزة إضافية' : 'إجادة العربية';
  if (hasEnglish) return 'إجادة الإنجليزية';
  return value;
}

export function createDashboardI18n(lang: Lang) {
  const messages = MESSAGE_SETS[lang];
  const locale = lang === 'ar' ? 'ar-QA' : 'en-QA';
  const formatters = FORMATTERS[lang];

  const number = (value: number) => formatters.number.format(value);
  const compactNumber = (value: number) => formatters.compact.format(value);
  const currency = (value: number) => lang === 'ar'
    ? `${formatters.number.format(value)} دولاراً أمريكياً`
    : formatters.currency.format(value);
  const percent = (value: number, digits = 1) =>
    (digits === 0 ? formatters.percent0 : formatters.percent1).format(value / 100);

  function t(key: DashboardMessageKey, values?: Record<string, string | number>) {
    return interpolate(messages[key], values);
  }

  function value(dimension: DashboardValueDimension, raw: unknown) {
    const text = String(raw ?? '');
    if (lang === 'en' || !text) return text;
    if (/^[\u0600-\u06ff]/.test(text)) return text;
    if (text === 'All') return ARABIC_LABELS.country?.All ?? text;
    if (dimension === 'timeline') return translateTimeline(text, value => formatters.year.format(value));
    if (dimension === 'experience') return translateExperience(text, number);
    if (dimension === 'language') return translateLanguage(text);
    return ARABIC_LABELS[dimension]?.[text] ?? text;
  }

  return { lang, dir: lang === 'ar' ? 'rtl' as const : 'ltr' as const, locale, t, value, number, compactNumber, currency, percent };
}

export function useDashboardI18n() {
  const { lang } = useLanguage();
  return useMemo(() => createDashboardI18n(lang), [lang]);
}

export type DashboardI18n = ReturnType<typeof createDashboardI18n>;
