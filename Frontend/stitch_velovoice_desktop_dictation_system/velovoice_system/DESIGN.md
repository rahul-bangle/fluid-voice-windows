---
name: VeloVoice System
colors:
  surface: '#f7f9fb'
  surface-dim: '#d8dadc'
  surface-bright: '#f7f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f6'
  surface-container: '#eceef0'
  surface-container-high: '#e6e8ea'
  surface-container-highest: '#e0e3e5'
  on-surface: '#191c1e'
  on-surface-variant: '#434655'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f3'
  outline: '#737686'
  outline-variant: '#c3c6d7'
  surface-tint: '#0053db'
  primary: '#004ac6'
  on-primary: '#ffffff'
  primary-container: '#2563eb'
  on-primary-container: '#eeefff'
  inverse-primary: '#b4c5ff'
  secondary: '#4648d4'
  on-secondary: '#ffffff'
  secondary-container: '#6063ee'
  on-secondary-container: '#fffbff'
  tertiary: '#943700'
  on-tertiary: '#ffffff'
  tertiary-container: '#bc4800'
  on-tertiary-container: '#ffede6'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dbe1ff'
  primary-fixed-dim: '#b4c5ff'
  on-primary-fixed: '#00174b'
  on-primary-fixed-variant: '#003ea8'
  secondary-fixed: '#e1e0ff'
  secondary-fixed-dim: '#c0c1ff'
  on-secondary-fixed: '#07006c'
  on-secondary-fixed-variant: '#2f2ebe'
  tertiary-fixed: '#ffdbcd'
  tertiary-fixed-dim: '#ffb596'
  on-tertiary-fixed: '#360f00'
  on-tertiary-fixed-variant: '#7d2d00'
  background: '#f7f9fb'
  on-background: '#191c1e'
  surface-variant: '#e0e3e5'
typography:
  headline-xl:
    fontFamily: Inter
    fontSize: 36px
    fontWeight: '700'
    lineHeight: 44px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  title-md:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 26px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-caps:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  mono-data:
    fontFamily: Geist
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px
  container-max: 1280px
  gutter: 20px
---

## Brand & Style

This design system is built on the principles of **Efficiency, Precision, and Integration**. It is designed for high-performance users who require an "AI-native" interface that feels like an extension of their existing workflow rather than a disruptive layer.

The visual style is **Corporate / Modern** with a lean toward functional minimalism. It emphasizes high-clarity information density, using a crisp white and light grey base to create a focused work environment. Unlike the ethereal nature of glassmorphism, this system utilizes solid, tactile surfaces and subtle depth to convey a sense of reliability and grounded intelligence. The emotional response is one of calm productivity—the UI should feel fast (Velo) and articulate (Voice).

## Colors

The palette is anchored by a **Vibrant Indigo primary**, signaling action and intelligence. 

- **Primary:** Used for main actions, active states, and focus indicators.
- **Surface Palette:** Employs a tiered light-grey system (`#F8FAFC` for backgrounds and `#FFFFFF` for elevated cards) to create a clean, non-distracting canvas.
- **Accents:** A secondary violet-blue is used sparingly for AI-specific features, such as transcription processing or insights.
- **Functional Neutrals:** Slate tones are used for typography to ensure high legibility without the harshness of pure black.

## Typography

The system utilizes **Inter** for its neutral, highly legible characteristic across all standard UI elements. For technical or AI-driven data points (like timestamps or word counts), **Geist** is introduced to provide a precise, developer-friendly "AI-native" feel.

Scale is used to enforce hierarchy:
- Use **Headline XL** only for primary dashboard greetings.
- Use **Label Caps** for category headers and sidebar labels to maintain a professional, organized structure.
- **Body SM** is the default for transcription text to maximize content density on the screen.

## Layout & Spacing

The layout follows a **Fixed-Fluid Hybrid** model. The sidebar remains at a fixed width of 260px, while the main content area utilizes a fluid grid that caps at 1280px to maintain readability.

- **Grid:** A 12-column layout for the main content area.
- **Rhythm:** A 4px base unit informs all padding and margins. 
- **Margins:** Desktop views use 32px external margins; mobile scales down to 16px.
- **Density:** High density is preferred for transcription logs, using 12px (sm) gaps between entries.

## Elevation & Depth

Hierarchy is established through **Tonal Layers** supplemented by **Ambient Shadows**.

1.  **Level 0 (Background):** Slate-50 (#F8FAFC).
2.  **Level 1 (Cards/Sidebar):** White (#FFFFFF) with a thin 1px border (#E2E8F0).
3.  **Level 2 (Modals/Popovers):** White with a soft, multi-layered shadow.
    - *Shadow Profile:* `0 4px 6px -1px rgb(0 0 0 / 0.05), 0 2px 4px -2px rgb(0 0 0 / 0.05)`.

This approach avoids the "floaty" feel of glassmorphism in favor of structural clarity. Surfaces should feel physical and distinct.

## Shapes

The design system uses a **Rounded** language to soften the professional tone and make the AI feel approachable.

- **Standard Components:** Buttons, inputs, and small cards use `0.5rem` (rounded-md).
- **Container Elements:** Large content areas and main dashboard cards use `1rem` (rounded-lg).
- **Interactive States:** Subtle 2px focus rings in the primary indigo color follow the border radius of the element.

## Components

### Buttons
- **Primary:** Solid Indigo background with white text. High contrast, no gradient.
- **Secondary:** Subtle grey stroke with Slate-900 text.
- **Tertiary:** Ghost style, appearing only on hover with a light grey background tint.

### Input Fields
- White background with a 1px Slate-200 border. 
- On focus, the border transitions to Primary Indigo with a soft 2px outer glow.
- Labels are always positioned above the input in **Label Caps**.

### Cards & Containers
- Cards use a white background and a very subtle 1px border. 
- Shadow is only applied when the card is "active" or "hovered" to indicate interactivity.

### Chips & Status
- Use highly desaturated versions of the primary color for background fills (e.g., Indigo-50) with high-contrast text for status indicators like "Synced" or "Processing".

### Navigation
- Vertical sidebar with active states indicated by a solid left-edge "accent bar" in Primary Indigo and a light Indigo-50 background fill for the entire row.