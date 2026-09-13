---
name: Precision Aerospace Guidance
colors:
  surface: '#0f131c'
  surface-dim: '#0f131c'
  surface-bright: '#353942'
  surface-container-lowest: '#0a0e16'
  surface-container-low: '#181c24'
  surface-container: '#1c2028'
  surface-container-high: '#262a33'
  surface-container-highest: '#31353e'
  on-surface: '#dfe2ee'
  on-surface-variant: '#c1c6d4'
  inverse-surface: '#dfe2ee'
  inverse-on-surface: '#2c3039'
  outline: '#8b919e'
  outline-variant: '#414752'
  surface-tint: '#a8c8ff'
  primary: '#a8c8ff'
  on-primary: '#003062'
  primary-container: '#0a66c2'
  on-primary-container: '#dbe6ff'
  inverse-primary: '#005eb5'
  secondary: '#92dbff'
  on-secondary: '#003547'
  secondary-container: '#00c4fd'
  on-secondary-container: '#004d66'
  tertiary: '#93ccff'
  on-tertiary: '#003351'
  tertiary-container: '#006ca4'
  on-tertiary-container: '#d2e8ff'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#d6e3ff'
  primary-fixed-dim: '#a8c8ff'
  on-primary-fixed: '#001b3d'
  on-primary-fixed-variant: '#00468a'
  secondary-fixed: '#bfe9ff'
  secondary-fixed-dim: '#6dd2ff'
  on-secondary-fixed: '#001f2a'
  on-secondary-fixed-variant: '#004d65'
  tertiary-fixed: '#cce5ff'
  tertiary-fixed-dim: '#93ccff'
  on-tertiary-fixed: '#001d31'
  on-tertiary-fixed-variant: '#004b73'
  background: '#0f131c'
  on-background: '#dfe2ee'
  surface-variant: '#31353e'
typography:
  hud-metric-lg:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '800'
    lineHeight: 52px
    letterSpacing: -0.03em
  hud-metric-lg-mobile:
    fontFamily: Inter
    fontSize: 38px
    fontWeight: '800'
    lineHeight: 42px
    letterSpacing: -0.03em
  hud-metric-md:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 38px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 30px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 26px
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 22px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: -0.005em
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0em
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: 0.005em
  label-telemetry:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 14px
    letterSpacing: 0.08em
  label-md:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Inter
    fontSize: 10px
    fontWeight: '600'
    lineHeight: 12px
    letterSpacing: 0.04em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-sm: 0.75rem
  margin: 1rem
  margin-lg: 1.5rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
---

## Brand & Style

This design system establishes an aerospace-grade geospatial experience engineered for mission-critical civilian and institutional navigation. The brand identity fuses the ergonomic polish of premium consumer navigation, the uncompromising cartographic legibility of global mapping platforms, and the high-density technical authority of automotive heads-up displays (HUDs).

The visual language balances restraint and hyper-precision:
- **Calibrated Restraint:** Surfaces recede to allow critical vector geometries, lane-level guidance, and situational telemetry to dominate the visual field.
- **Atmospheric Depth:** Multi-tiered frosted glassmorphic panels simulate flight-deck instrumentation, elevating critical route maneuvers over dynamic cartography without visual fragmentation.
- **Tactical Clarity:** High-contrast typographic hierarchies and deterministic status chromas communicate split-second system states—specifically satellite fix health, dead reckoning confidence, and inertial sensor fusion.

The system addresses field researchers, urban commuters, transport logistics operators, and technical observers who demand rapid cognitive decoding at highway speeds or under adverse lighting conditions.

## Colors

The palette operates across dual contextual modes, with the default set to high-contrast dark mode to conserve OLED energy, prevent nighttime vision blinding, and reflect cockpit-style instrumentation.

### System Chromas
- **Primary Electric Azure (`#0A66C2`):** Defines the primary vehicle heading glyph, optimal route vectors, and focal interaction targets.
- **Secondary Electric Cyan (`#00C6FF`):** Powers maneuver turn vectors, predictive waypoint arcs, and active velocity indicators.
- **Tertiary NavSat Azure (`#0284C7`):** Anchors secondary telemetry readouts, selected route alternative lines, and focus states.
- **Neutral Obsidian (`#0B0F17`):** The foundational dark base substrate, preventing pure-black OLED smearing while maintaining absolute contrast.

### Sensor & Telemetry Status Palette
- **GNSS Nominal / Healthy (`#10B981`):** Multi-constellation RTK/NavIC lock with low Dilution of Precision (DOP < 1.5).
- **GNSS Degraded / Multipath (`#F59E0B`):** Satellite signal degradation, ionospheric delay, or partial urban canyon obstruction.
- **GNSS Critical / Denied (`#EF4444`):** Complete satellite signal loss; alert threshold triggered.
- **IDR Active (Intelligent Dead Reckoning) (`#00D2FF` to `#0284C7`):** Inertial odometry, wheel ticks, and visual SLAM active.
- **Telemetry Inactive / Muted Slate (`#94A3B8`):** Dormant secondary sensors and historical trails.

### Surface Architectures
- **Dark Glass Canvas:** `rgba(11, 15, 23, 0.82)` paired with `rgba(255, 255, 255, 0.08)` hairline interior rim strokes and `backdrop-filter: blur(20px) saturate(180%)`.
- **Light Glass Canvas:** `rgba(248, 250, 252, 0.84)` paired with `rgba(15, 23, 42, 0.06)` hairline border strokes and `backdrop-filter: blur(20px) saturate(160%)`.

## Typography

Typography relies entirely on the technical clarity, neutral grotesque geometry, and robust x-height of **Inter**.

- **Tabular Figures & Optics:** All telemetry readouts, velocity dials, dynamic maneuver distances (e.g., `450 m`), and ETA timestamps require OpenType feature `'tnum'` (tabular figures) and `'cv05'` enabled. This prevents horizontal layout jitter during high-frequency GPS coordinate changes.
- **Glanceability Index:** Display metrics (`hud-metric-*`) use aggressive negative letter spacing to preserve physical bounding area while remaining visible from arm’s-length dashboard docks.
- **Technical Telemetry:** The `label-telemetry` token applies an uppercase optical tracking offset (`+0.08em`) to guarantee immediate separation between raw sensor metrics (e.g., `HDOP: 0.8`, `SAT: 14/18`) and standard cartographic road labels.

## Layout & Spacing

The layout model is governed by a 4px/8px hybrid spatial system optimized for dynamic gesture zones and thumb-reach zones within mobile viewport viewports.

### Grid & Canvas Composition
- **Map Viewport (Canvas 0):** Unbounded, full-bleed coordinate canvas.
- **HUD Layer (Canvas 1):** Bounded by strict screen margins (`margin` = 16px).
  - **Top Edge Clearance:** Safe-area top padding + 8px gap for the Floating Search / Maneuver Banner.
  - **Right Control Column:** 48px-wide vertical stacked action matrix positioned 16px from the right boundary.
  - **Bottom Active Sheet:** Segmented drag modal anchored flush or offset by 12px margins depending on expansion tier.
- **Breakpoints:**
  - **Compact Phone (< 600px):** Single-column layout. Top search/maneuver full width minus margins; bottom sheet occupies 100% width.
  - **Foldable / Tablet / In-Dash Screen (600px - 1024px):** Split layout; dynamic HUD floating left with maximum 380px panel width; cartographic controls cluster right-aligned.

### Layout Distances
Margins around floating overlay modules must consistently match `margin` (`1rem`) to maintain parallel alignment with native device boundaries. Gaps between grouped controls utilize `space-sm` (`0.5rem`).

## Elevation & Depth

Visual depth is achieved through optical refraction, multi-stage backdrop blurs, and luminous perimeter rims rather than heavy physical drop shadows. This preserves tactical clarity over bright satellite imagery and complex vector topologies.

### Elevation Architecture
1. **Level 0 (Cartographic Basemap):** Vector tiles, traffic heatmap overlays, polyline routes, 3D building extrusions.
2. **Level 1 (Map Markers & Pins):** High-contrast circular markers, geo-fences, waypoint rings with glowing ambient auras:
   - Subtle outer glow: `0 0 12px rgba(0, 198, 255, 0.45)`.
3. **Level 2 (Floating Action Controls & Badges):** Translucent circular map widgets (re-center, layer toggles, compass):
   - Background: `rgba(11, 15, 23, 0.72)`
   - Backdrop blur: `16px`
   - Perimeter rim: `1px solid rgba(255, 255, 255, 0.12)`
   - Ambient shadow: `0 8px 24px -4px rgba(0, 0, 0, 0.4)`
4. **Level 3 (Tactical Overlays & Maneuver Banners):** Floating turn-by-turn instruction panels:
   - Background: `rgba(11, 15, 23, 0.88)`
   - Backdrop blur: `24px`
   - Top-lit highlight: Inner hairline shadow `inset 0 1px 0 rgba(255, 255, 255, 0.15)`
   - Soft drop shadow: `0 16px 32px -8px rgba(0, 0, 0, 0.6)`
5. **Level 4 (Modal Drawers & Emergency Overlays):** Interactive bottom sheets and system override sheets:
   - Surface: Multi-pass frosted obsidian glass with directional light gradient from top-left.
   - Deep ambient falloff: `0 -12px 40px rgba(0, 0, 0, 0.75)`.

## Shapes

The design system enforces a **Level 2 (Rounded)** shape configuration, deploying calibrated corner smoothing (squircle curvature) that visually echoes modern vehicle dashboard clusters and high-precision consumer devices.

### Curvature Matrix
- **Base Components (Badges, Buttons, Mini-cards):** `rounded` (8px / `0.5rem`).
- **Standard Floating Modules (Maneuver Banner, Search Bar, Dialogs):** `rounded-lg` (16px / `1rem`).
- **Bottom Sheets (Top Left/Right):** `rounded-xl` (24px / `1.5rem`) on leading edges.
- **Tactical Action Buttons & Floating Icon Nodes:** Strict circular pills (`rounded-full` / 9999px) to establish instant optical distinction from informational cards.
- **Telemetry Chips & Micro Status Pills:** `rounded-full` with 3px horizontal visual balance padding.

## Components

### 1. Maneuver Guidance Banner
- **Structure:** Floating header card offset by `margin`. Dual-section visual layout:
  - **Left Aspect (Action Glyph):** High-visibility turn icon rendered in `#00C6FF`, sized at 36x36px within an optical container.
  - **Right Aspect (Vector Info):** Maneuver distance (`hud-metric-md`) stacked over primary street label (`headline-sm`).
  - **Sub-strip (Lane Guidance):** Micro-lane indicator dots/arrows directly beneath, showing optimal lane highlighting in `#00C6FF` against inactive gray lane paths (`rgba(255, 255, 255, 0.25)`).
- **Surface:** Obsidian frosted glass (`rgba(11, 15, 23, 0.90)`), 1px stroke `rgba(255, 255, 255, 0.1)`.

### 2. IDR & GNSS Telemetry Badges
- **Visual Spec:** Dual-component pill indicator housing dynamic state changes.
- **GNSS Mode:** Left indicator dot (6px) with an active pulse animation using status chromas (`#10B981`, `#F59E0B`, or `#EF4444`). Followed by uppercase label `label-telemetry` (e.g., `GNSS LOCK: 3D`).
- **IDR Active Badge:** Electric cyan background tint (`rgba(0, 198, 255, 0.12)`), perimeter stroke (`rgba(0, 198, 255, 0.4)`), display text `IDR ENGAGED: 98% CONFIDENCE`.

### 3. Floating Glass Search Bar
- **Resting State:** Floating capsule `rounded-lg`, height 52px, containing a search glyph, placeholder text (`body-md`), a microphone icon, and a NavIC dual-frequency indicator chip.
- **Focus / Typing State:** Seamlessly expands into full overlay sheet with keyboard elevation; ambient border illuminates with a 1px glow in Primary Blue (`#0A66C2`).

### 4. Floating Circular Map Actions
- **Geometry:** 44px x 44px circular pills stacked vertically with `space-sm` (8px) inter-button separation.
- **Controls:** Compass needle (with true-north red accent), Recenter / 3D Tilt toggle, Layer Selector, Traffic Density toggle.
- **Active / Pressed State:** Inner surface transitions from `rgba(11, 15, 23, 0.72)` to `#0A66C2` with active icon swapping to pure `#FFFFFF`.

### 5. Multi-Tier Bottom Sheet
- **Handle:** Fluid drag handle (36px wide, 4px height, `rgba(255, 255, 255, 0.3)`), centered at `space-xs` from the top.
- **State 1 (Collapsed Glance):** ETA metric (`hud-metric-lg-mobile`), remaining distance, and dynamic delay pill (`+4 min` in `#EF4444`). Quick-action primary button: "Start Route".
- **State 2 (Half Expand):** Step-by-step cue list, route elevation graph, and sensor diagnostics panel.
- **State 3 (Full Expand):** Alternate route comparison tiles, waypoint injection controls, and detailed satellite signal breakdown.

### 6. Interactive Controls & Buttons
- **Primary Nav Button:** Height 52px, `rounded-lg`, background solid `#0A66C2`, text `#FFFFFF` (`label-md`). Tap feedback scales to `0.98` with continuous active surface lightening.
- **Secondary Action Button:** Height 44px, `rounded-lg`, background `rgba(255, 255, 255, 0.08)`, border `rgba(255, 255, 255, 0.15)`, text `#FFFFFF`.
- **Toggle Switches & Checkboxes:** Micro-switches with smooth 200ms cubic-bezier translation; active track illuminates in `#0A66C2`, thumb cap stays porcelain white `#F8FAFC`.
- **Settings Rows:** Monochromatic clean layouts with 16px vertical padding, separated by `rgba(255, 255, 255, 0.06)` hairline dividers, finished with trailing chevron accessories.