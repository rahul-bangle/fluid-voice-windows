---
name: VeloVoice
colors:
  surface: '#131317'
  surface-dim: '#131317'
  surface-bright: '#39393d'
  surface-container-lowest: '#0e0e12'
  surface-container-low: '#1b1b1f'
  surface-container: '#1f1f23'
  surface-container-high: '#2a292e'
  surface-container-highest: '#353439'
  on-surface: '#e4e1e7'
  on-surface-variant: '#c2c6d6'
  inverse-surface: '#e4e1e7'
  inverse-on-surface: '#303034'
  outline: '#8c909f'
  outline-variant: '#424754'
  surface-tint: '#adc6ff'
  primary: '#adc6ff'
  on-primary: '#002e6a'
  primary-container: '#4d8eff'
  on-primary-container: '#00285d'
  inverse-primary: '#005ac2'
  secondary: '#4edea3'
  on-secondary: '#003824'
  secondary-container: '#00a572'
  on-secondary-container: '#00311f'
  tertiary: '#d0bcff'
  on-tertiary: '#3c0091'
  tertiary-container: '#a078ff'
  on-tertiary-container: '#340080'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#d8e2ff'
  primary-fixed-dim: '#adc6ff'
  on-primary-fixed: '#001a42'
  on-primary-fixed-variant: '#004395'
  secondary-fixed: '#6ffbbe'
  secondary-fixed-dim: '#4edea3'
  on-secondary-fixed: '#002113'
  on-secondary-fixed-variant: '#005236'
  tertiary-fixed: '#e9ddff'
  tertiary-fixed-dim: '#d0bcff'
  on-tertiary-fixed: '#23005c'
  on-tertiary-fixed-variant: '#5516be'
  background: '#131317'
  on-background: '#e4e1e7'
  surface-variant: '#353439'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '700'
    lineHeight: '1.1'
    letterSpacing: -0.04em
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: -0.03em
  headline-sm:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: '1.4'
    letterSpacing: -0.02em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
    letterSpacing: -0.01em
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.5'
    letterSpacing: '0'
  label-caps:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '600'
    lineHeight: '1'
    letterSpacing: 0.05em
  mono-data:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: '1.4'
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 4px
  container-padding: 24px
  gutter: 16px
  element-gap-sm: 8px
  element-gap-md: 16px
---

## Brand & Style

The design system is engineered for professional speed and cognitive clarity. It targets power users—developers, executives, and writers—who require an AI-native interface that feels "invisible" yet powerful. 

The aesthetic is **Hyper-Glassmorphism**. It leverages the depth of the OS layer, utilizing high-translucency frosted glass, vibrant background blurs, and micro-glows to indicate AI processing states. The interface should feel like a lightweight utility floating above the user's workflow, emphasizing an "instant" 62ms response feel through snappy transitions and high-fidelity visual feedback.

## Colors

The system defaults to a sophisticated **Obsidian Dark Mode** to reduce eye strain during long sessions. 

- **Primary (Electric Blue):** Used for focus states, primary actions, and active recording indicators.
- **Secondary (Emerald Green):** Reserved exclusively for "Active AI" states, successful voice-to-text processing, and connectivity status.
- **Tertiary (Amethyst):** Used sparingly for "Magic" features or experimental AI modes.
- **Neutrals:** The dark palette utilizes a deep obsidian base with progressively lighter translucent overlays to create hierarchy. The light mode variant uses a crisp off-white for high-contrast legibility.

## Typography

The system utilizes **Inter** for its systematic, utilitarian clarity. To achieve a high-performance "technical" look, tracking (letter-spacing) is tightened on larger headings. 

**JetBrains Mono** is introduced for labels, status indicators, and the vocabulary manager to reinforce the precision-tool nature of the application. All text should be rendered with `antialiased` smoothing to maintain legibility against translucent, blurred backgrounds.

## Layout & Spacing

This design system follows a **Fixed-Fluid Hybrid** model optimized for desktop utility. 
- **Floating Main UI:** A central floating pill or compact window (400px - 600px width) with 24px internal padding.
- **Sidebar Overlays:** Translucent panels slide in from the right for vocabulary management and settings, using 100% height of the app container.
- **Data Tables:** For the vocabulary manager, a dense layout with 8px vertical cell padding and 16px horizontal padding ensures high information density.

All spacing is derived from a 4px baseline grid to ensure pixel-perfect alignment of glass edges.

## Elevation & Depth

Hierarchy is established through **Backdrop Saturation and Blur** rather than traditional dropshadows.

1.  **Level 0 (Base):** Deep Obsidian (#0D0D11).
2.  **Level 1 (Main UI):** 60% opacity background with a 20px backdrop blur and a 1px inner border (#FFFFFF10).
3.  **Level 2 (Popovers/Tooltips):** 80% opacity background with a 30px backdrop blur and a subtle outer glow using the primary color at 10% opacity.
4.  **The "Active" Glow:** When recording, the main container gains a 2px external bloom (blur: 15px) in Emerald Green to provide peripheral status awareness.

## Shapes

The design system uses **Rounded (0.5rem / 8px)** geometry for standard components to maintain a modern, friendly but professional feel. 

- **Primary Pills:** Use the `rounded-xl` (1.5rem / 24px) setting for the main dictation bar and floating status indicators to distinguish them from standard utility windows.
- **Input Fields/Buttons:** Use the standard 8px radius.
- **Data Rows:** In the vocabulary manager, rows use a 4px radius on hover states to maintain a structured, table-centric appearance.

## Components

- **Floating Bar:** The core interface. A high-translucency capsule containing the waveform, mode selector, and status. It uses a "glass-morphism" stack: blur, then noise texture (2%), then tint.
- **Waveform:** An SVG-based dynamic component. High-frequency peaks in Electric Blue, transitioning to Emerald Green when speech is detected.
- **Segmented Controls:** Used for switching between "Prose," "Code," and "Chat" modes. Active states should feature a "sliding glass" effect with a subtle glow.
- **Buttons:** 
  - *Primary:* Solid Electric Blue with a white label. 
  - *Secondary:* Ghost style with 1px translucent border and a heavy backdrop blur.
- **Data Tables:** Used for Vocabulary management. Features sticky headers, monospaced text for technical terms, and "Action on Hover" patterns to keep the UI clean.
- **Input Fields:** Minimalist design with only a bottom border that illuminates to Electric Blue on focus. Background is a slightly lighter translucent obsidian.