# Frontend Redesign Design Spec

## Overview

Redesign the Backing stock trading system frontend using a Mastercard-inspired professional financial style. The goal is to apply warm cream surfaces, pill/rounded aesthetics, and the Mastercard color language while preserving the data density and professional feel required of a financial application.

**Current State**: Apple-inspired minimal design with blue accent (#0071e3), white backgrounds, and standard border-radius.

**Target State**: Mastercard-inspired editorial warmth with cream canvas, Ink Black CTAs, generous border-radius (20-40px), and professional financial data presentation.

---

## 1. Design System

### Color Palette

| Token | Hex | Usage |
|-------|-----|-------|
| `--color-canvas` | `#F3F0EE` | Page background - warm putty cream |
| `--color-canvas-lifted` | `#FCFBFA` | Card backgrounds - elevated surfaces |
| `--color-ink` | `#141413` | Primary text, primary CTAs, footer |
| `--color-accent` | `#CF4500` | Signal Orange - consent/legal only |
| `--color-accent-light` | `#F37338` | Light Signal Orange - decorative arcs only |
| `--color-up` | `#FF3B30` | Stock price up (China standard) |
| `--color-down` | `#34C759` | Stock price down |
| `--color-flat` | `#86868B` | Unchanged price |
| `--color-success` | `#34C759` | Success states |
| `--color-danger` | `#FF3B30` | Error/danger states |
| `--color-warning` | `#F79E1B` | Warning states |
| `--color-text-secondary` | `#696969` | Muted text (Slate Gray) |
| `--color-border` | `rgba(0,0,0,0.06)` | Subtle borders |

**Important**: Signal Orange (`#CF4500`) is reserved ONLY for consent actions and legal operations. Do NOT use for marketing CTAs.

### Typography

**Font Family**:
```css
font-family: 'Sofia Sans', -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
```

**Fallback rationale**: Sofia Sans is the closest open-source match to Mastercard's MarkForMC, already in their declared fallback stack.

**Type Scale** (existing, preserved):
| Role | Size | Weight | Letter Spacing |
|------|------|--------|----------------|
| H1 (hero) | 28px | 600 | -0.02em |
| H2 (section) | 24px | 600 | -0.02em |
| Card title | 17px | 600 | -0.01em |
| Body | 14px | 450 | normal |
| Nav/Button | 14px | 500 | -0.02em |
| Small | 13px | 450 | normal |
| Caption | 11px | 600 | 0.05em |

**Key**: Body text uses weight 450 (Sofia Sans variable) for softer readability, not 400.

### Border Radius System

| Token | Value | Usage |
|-------|-------|-------|
| `--radius-sm` | `6px` | Tiny decorative |
| `--radius-btn` | `20px` | Primary/secondary buttons |
| `--radius-card` | `40px` | Hero media, large card corners |
| `--radius-pill` | `999px` | Navigation, chips, badges |

**Rule**: Skip middle ground (8-16px). Use either small (≤6), medium-large (20-40), or full-pill (99+).

### Shadows

| Level | Value | Usage |
|-------|-------|-------|
| 1 (soft) | `rgba(0,0,0,0.04) 0px 4px 24px 0px` | Floating nav pill |
| 2 (card) | `rgba(0,0,0,0.08) 0px 24px 48px 0px` | Card hover, elevated elements |

**Philosophy**: Shadows are atmospheric cushioning with 48px+ spread and ≤10% opacity. No hard-edged tight shadows.

### Spacing Scale

Base unit: 8px
Scale: 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 / 96

---

## 2. Navigation

### Desktop: Floating Pill Navigation

```
┌─────────────────────────────────────────────────────────────────┐
│                      [24px from viewport top]                   │
│    ┌─────────────────────────────────────────────────────────┐   │
│    │  Logo  │  仪表盘  股票管理  自选股  筛选  策略  AI分析  │ 🔍 │   │
│    └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

- Container: white background, `--shadow-soft`, `--radius-pill`
- Position: fixed 24px from top, horizontally centered
- Padding: ~16px vertical, ~40px horizontal
- Link style: Ink Black, weight 500, 14px, no underline
- Active indicator: Signal Orange dot below link (not background highlight)
- Hover: subtle background `rgba(0,0,0,0.04)`
- Search: circular icon button, 48px diameter

### Mobile: Full-Screen Overlay

- Hamburger + Logo + Search icon in compact pill
- Menu opens as full-screen overlay with dark backdrop
- Links stacked vertically, 48px+ touch targets
- Same pill aesthetic, scaled down

---

## 3. Component Transformations

### Cards

| Before | After |
|--------|-------|
| White background | Canvas Lifted (`#FCFBFA`) |
| 1px border `--color-border` | No border |
| Shadow: `0 1px 2px rgba(0,0,0,0.04)` | Shadow Level 2 on hover |
| Border-radius: 16px | Border-radius: 40px (large cards), 20px (small cards) |

### Primary Button (Ink Pill)

```css
background: var(--color-ink);      /* #141413 */
color: var(--color-canvas);        /* #F3F0EE - not pure white */
border: 1.5px solid var(--color-ink);
border-radius: var(--radius-btn);  /* 20px */
padding: 6px 24px;
font-weight: 500;
letter-spacing: -0.02em;
```

### Secondary Button (Outlined Pill)

```css
background: white;
color: var(--color-ink);
border: 1.5px solid var(--color-ink);
border-radius: var(--radius-btn);
```

### Tables

| Before | After |
|--------|-------|
| White background | Lifted Canvas (`#FCFBFA`) |
| Gray row hover | Subtle shadow on row hover |
| Tight row height | Comfortable padding (12px vertical) |
| Header: uppercase gray | Header: Slate Gray, uppercase, letter-spacing +4% |

### Input Fields

```css
background: transparent;
border: 1px solid var(--color-ink);
border-radius: var(--radius-pill);  /* Full pill for search */
opacity: 0.5 on border initially
focus: opacity 1, subtle shadow ring
```

### Badges/Tags

```css
border-radius: var(--radius-pill);  /* Full pill, not small radius */
padding: 2px 10px;
font-size: 12px;
font-weight: 500;
```

---

## 4. Page-Specific Guidance

### Dashboard

- Page background: Canvas (`#F3F0EE`)
- Index cards (上证指数、深证成指等): Large 40px radius, cream-lifted background
- Trend chart: White card with 40px radius, Light Signal Orange decorative arc optional
- Market stats sidebar: stat cards with large numbers
- Watchlist table: Cream-lifted background, 40px container radius

### AgentAnalysis

- Stock search: Full pill input
- Mode selector: Pill button group
- Progress stages: Large cards with stage indicators
- Decision card: Prominent display with Ink Black CTA buttons
- History table: Standard table styling

### StockChart

- Chart area: Canvas background (not white)
- Controls: Ink Black pill buttons
- Sidebar panels: Cream-lifted cards

### StockList / Screener / Watchlist

- Table container: 40px radius card
- Filter bar: Pill button groups for active filters
- Pagination: Subtle, minimal styling

### Backtest / BacktestHistory

- Form sections: Lifted cream cards with 40px radius
- Results table: Standard cream-lifted styling
- Charts: Canvas background with Ink Black controls

### Strategies

- Strategy cards: Large 40px radius
- Primary CTA: Ink Black pill
- Secondary actions: Outlined pill

---

## 5. Ant Design Overrides

Override Ant Design defaults to match Mastercard aesthetic:

```css
/* Cards */
.ant-card {
  border-radius: 40px !important;
  border: none !important;
  background: var(--color-canvas-lifted) !important;
  box-shadow: var(--shadow-card) !important;
}

/* Buttons */
.ant-btn-primary {
  background: var(--color-ink) !important;
  border-color: var(--color-ink) !important;
  border-radius: var(--radius-btn) !important;
  font-weight: 500 !important;
}

.ant-btn-default {
  border-radius: var(--radius-btn) !important;
  border-color: var(--color-ink) !important;
}

/* Inputs */
.ant-input,
.ant-input-affix-wrapper,
.ant-select-selector {
  border-radius: var(--radius-btn) !important;
  border-color: rgba(20,20,19,0.3) !important;
}

/* Tables */
.ant-table {
  background: transparent !important;
}

.ant-table-thead > tr > th {
  background: var(--color-canvas) !important;
  border-bottom: 1px solid var(--color-border) !important;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-secondary) !important;
}

.ant-table-tbody > tr:hover > td {
  background: var(--color-canvas) !important;
}

/* Select/Dropdown */
.ant-select-dropdown {
  border-radius: var(--radius-card) !important;
  overflow: hidden;
}

/* Modal */
.ant-modal-content {
  border-radius: 40px !important;
  background: var(--color-canvas-lifted) !important;
}

/* Progress */
.ant-progress-inner {
  border-radius: var(--radius-pill) !important;
}
```

---

## 6. Responsive Breakpoints

| Name | Width | Key Changes |
|------|-------|-------------|
| Mobile | ≤ 767px | Compact pill nav, hamburger menu, single-column layout, 48px touch targets |
| Tablet | 768-1023px | 2-column grids, truncated nav links |
| Desktop | ≥ 1024px | Full floating pill nav, multi-column layouts |

---

## 7. Implementation Phases

### Phase 1: Design System Foundation
- Rewrite `index.css` with all CSS custom properties
- Create `App.tsx` with floating pill navigation
- Add Sofia Sans font import
- Ant Design theme overrides

### Phase 2: Core Pages
- `Dashboard.tsx` - Card radius, colors, index cards
- `AgentAnalysis.tsx` - Button styles, progress cards

### Phase 3: Data Pages
- `StockList.tsx`
- `Screener.tsx`
- `Watchlist.tsx`
- `StockChart.tsx`

### Phase 4: Operation Pages
- `Backtest.tsx`
- `BacktestHistory.tsx`
- `Strategies.tsx`

### Phase 5: Polish
- Empty states
- Loading states
- Error states
- Mobile menu

---

## 8. File Changes Summary

| File | Changes |
|------|---------|
| `frontend/src/index.css` | Full rewrite with CSS variables, component styles |
| `frontend/src/App.tsx` | Floating pill nav, mobile overlay menu |
| `frontend/src/pages/*.tsx` | 10 pages - card radius, button styles, colors |
| `frontend/src/components/StockSearch.tsx` | Pill-style search input |

---

## 9. Design Principles

**Do:**
- Use Canvas Cream (`#F3F0EE`) as page background
- Apply 40px radius to large containers, 20px to buttons
- Keep primary CTAs as Ink Black pills
- Use weight 450 for body text (Sofia Sans)
- Maintain data density and professional financial feel
- Use Signal Orange ONLY for consent/legal actions

**Don't:**
- Use pure white (`#FFFFFF`) for page backgrounds
- Use blue (`#0071e3`) for any UI elements
- Use middle-ground radius (8-16px)
- Use Signal Orange for marketing CTAs
- Add hard shadows or tight spread shadows
- Use uppercase for anything except eyebrow labels
