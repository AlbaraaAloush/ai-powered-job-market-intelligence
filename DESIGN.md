# Mihna Product Design System

## Theme

Mihna product surfaces use the landing identity as a restrained research workspace. The visual language is instrument-like, full-bleed, and editorial in its hierarchy, while controls remain conventional and compact.

## Color

- Canvas: `oklch(0.985 0.005 220)` light, `oklch(0.13 0.012 220)` dark
- Surface: `oklch(1 0 0)` light, `oklch(0.165 0.013 220)` dark
- Recessed surface: `oklch(0.965 0.006 220)` light, `oklch(0.19 0.014 220)` dark
- Ink: `oklch(0.16 0.018 220)` light, `oklch(0.965 0.006 220)` dark
- Muted ink: `oklch(0.42 0.015 220)` light, `oklch(0.72 0.012 220)` dark
- Primary: deep instrument blue, shared with the landing experience
- Accent: warm amber reserved for limited emphasis, not navigation or decoration

## Typography

- Product UI and body: Geist
- Data and compact metadata: Geist Mono
- Mihna wordmark and rare page-level display moments: Fraunces in English, Reem Kufi in Arabic
- Product headings use restrained fixed sizes; display typography is not used for controls or dense data.

## Shape

- Panels and fields: 10-14px radius
- Buttons: pill only for global navigation and compact actions; otherwise 10px radius
- Borders are hairlines used for structure, not paired with broad decorative shadows

## Layout

- Application routes fill at least `100dvh`
- A compact top rail provides brand, route navigation, language, and theme
- Dataset and model controls occupy a collapsible side rail where required
- Main work areas are full-bleed and independently scrollable
- No application footer

## Motion

Use 150-220ms transitions for navigation, panels, and state feedback. Motion communicates state only and must collapse under reduced-motion preferences.

## Components

- `AppShell`: shared top rail and optional control sidebar
- `AppNavigation`: Dashboard, Chat, Analyze with route-aware active state
- `Sidebar`: dataset and model scope controls
- `Dashboard`: existing dashboard behavior in the new visual system
- `Chat`: existing RAG behavior in a dedicated route and focused conversation layout
- `AnalyzePlaceholder`: clear future-state page with no simulated functionality
