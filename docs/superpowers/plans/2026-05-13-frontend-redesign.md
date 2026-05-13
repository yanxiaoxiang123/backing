# Frontend Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the Backing stock trading system frontend from Apple-inspired blue/white to Mastercard-inspired warm cream + Ink Black aesthetic across all 10 pages.

**Architecture:** Global CSS design system with CSS custom properties, unified component overrides for Ant Design, floating pill navigation, and per-page style refinements. All changes are additive/non-destructive - no component logic changes.

**Tech Stack:** React + Vite, Ant Design, ECharts, Sofia Sans (Google Fonts), CSS Custom Properties

---

## File Change Map

| File | Changes |
|------|---------|
| `frontend/src/index.css` | Full rewrite - CSS variables, base styles, Ant Design overrides |
| `frontend/src/App.tsx` | Floating pill navigation, mobile overlay |
| `frontend/src/pages/Dashboard.tsx` | Card radius, colors, layout refinements |
| `frontend/src/pages/AgentAnalysis.tsx` | Button styles, progress cards, decision display |
| `frontend/src/pages/StockList.tsx` | Table container styling |
| `frontend/src/pages/Screener.tsx` | Table container, filter pills |
| `frontend/src/pages/Watchlist.tsx` | Table container styling |
| `frontend/src/pages/StockChart.tsx` | Chart controls, sidebar cards |
| `frontend/src/pages/Backtest.tsx` | Form cards, CTA buttons |
| `frontend/src/pages/BacktestHistory.tsx` | Table styling |
| `frontend/src/pages/Strategies.tsx` | Strategy cards, CTAs |
| `frontend/src/pages/DLPrediction.tsx` | Card styling, buttons |
| `frontend/src/components/StockSearch.tsx` | Pill-style search input |

---

## Task 1: Design System Foundation - index.css

**Files:**
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Replace entire file content with new design system CSS**

```css
/*** Backing - Mastercard-inspired Design System ***/

/* Font Import */
@import url('https://fonts.googleapis.com/css2?family=Sofia+Sans:wght@400;450;500;600;700&display=swap');

/* ============================================
   1. CSS Custom Properties (Design Tokens)
   ============================================ */
:root {
  /* Primary Surfaces */
  --color-canvas: #F3F0EE;           /* Page background - warm putty cream */
  --color-canvas-lifted: #FCFBFA;     /* Card backgrounds - elevated surfaces */
  --color-white: #FFFFFF;             /* Navigation, modals, select backgrounds */

  /* Brand Colors */
  --color-ink: #141413;               /* Primary text, primary CTAs, footer */
  --color-charcoal: #262627;          /* Secondary text variant */
  --color-accent: #CF4500;           /* Signal Orange - consent/legal ONLY */
  --color-accent-light: #F37338;      /* Light Signal Orange - decorative arcs */
  --color-clay: #9A3A0A;              /* Deep rust - secondary link buttons */

  /* Stock Semantic Colors */
  --color-up: #FF3B30;               /* Stock price up (China standard) */
  --color-down: #34C759;              /* Stock price down */
  --color-flat: #86868B;              /* Unchanged price */

  /* Functional Colors */
  --color-success: #34C759;
  --color-success-light: rgba(52, 199, 89, 0.1);
  --color-danger: #FF3B30;
  --color-danger-light: rgba(255, 59, 48, 0.1);
  --color-warning: #F79E1B;
  --color-warning-light: rgba(247, 158, 27, 0.1);

  /* Text Colors */
  --color-text-primary: var(--color-ink);
  --color-text-secondary: #696969;    /* Slate Gray */
  --color-text-tertiary: #D1CDC7;     /* Dust Taupe - whisper text */

  /* Borders */
  --color-border: rgba(0, 0, 0, 0.06);
  --color-border-medium: rgba(0, 0, 0, 0.12);

  /* Shadows */
  --shadow-nav: rgba(0, 0, 0, 0.04) 0px 4px 24px 0px;
  --shadow-card: rgba(0, 0, 0, 0.08) 0px 24px 48px 0px;
  --shadow-hover: rgba(0, 0, 0, 0.12) 0px 24px 48px 0px;

  /* Border Radius Scale */
  --radius-sm: 6px;
  --radius-btn: 20px;
  --radius-card: 40px;
  --radius-pill: 999px;

  /* Spacing Scale */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;
  --space-2xl: 48px;
  --space-3xl: 64px;

  /* Typography */
  --font-family: 'Sofia Sans', -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
  --font-size-xs: 11px;
  --font-size-sm: 13px;
  --font-size-base: 14px;
  --font-size-md: 17px;
  --font-size-lg: 20px;
  --font-size-xl: 24px;
  --font-size-2xl: 28px;
  --font-size-3xl: 34px;

  /* Transitions */
  --transition-fast: 0.15s ease;
  --transition-normal: 0.25s ease;
  --transition-slow: 0.4s ease;
}

/* ============================================
   2. Reset & Base
   ============================================ */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html {
  scroll-behavior: smooth;
}

body {
  font-family: var(--font-family);
  font-size: var(--font-size-base);
  font-weight: 450;
  color: var(--color-text-primary);
  background: var(--color-canvas);
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

#root {
  min-height: 100vh;
}

a {
  color: var(--color-ink);
  text-decoration: none;
}

a:hover {
  text-decoration: underline;
}

/* ============================================
   3. Layout
   ============================================ */
.app-layout {
  min-height: 100vh;
  background: var(--color-canvas);
}

.app-content {
  max-width: 1280px;
  margin: 0 auto;
  padding: var(--space-xl) var(--space-lg);
}

/* ============================================
   4. Floating Pill Navigation
   ============================================ */
.nav-pill-container {
  position: fixed;
  top: 24px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 1000;
  width: calc(100% - 96px);
  max-width: 1200px;
}

.nav-pill {
  background: var(--color-white);
  border-radius: var(--radius-pill);
  box-shadow: var(--shadow-nav);
  padding: var(--space-sm) var(--space-lg);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-md);
}

.nav-logo {
  font-size: var(--font-size-md);
  font-weight: 600;
  color: var(--color-ink);
  letter-spacing: -0.02em;
  white-space: nowrap;
  cursor: pointer;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  flex: 1;
  justify-content: center;
}

.nav-item {
  padding: var(--space-sm) var(--space-md);
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--color-text-secondary);
  text-decoration: none;
  border-radius: var(--radius-pill);
  transition: all var(--transition-fast);
  cursor: pointer;
  position: relative;
  white-space: nowrap;
}

.nav-item:hover {
  color: var(--color-ink);
  background: rgba(0, 0, 0, 0.04);
  text-decoration: none;
}

.nav-item.active {
  color: var(--color-ink);
  font-weight: 500;
}

.nav-item.active::after {
  content: '';
  position: absolute;
  bottom: -2px;
  left: 50%;
  transform: translateX(-50%);
  width: 4px;
  height: 4px;
  background: var(--color-accent);
  border-radius: 50%;
}

.nav-search-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: none;
  background: transparent;
  color: var(--color-ink);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-fast);
}

.nav-search-btn:hover {
  background: rgba(0, 0, 0, 0.04);
}

/* Mobile Navigation */
.nav-mobile-toggle {
  display: none;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: none;
  background: transparent;
  cursor: pointer;
  align-items: center;
  justify-content: center;
}

.nav-mobile-overlay {
  display: none;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(20, 20, 19, 0.95);
  z-index: 999;
  padding: var(--space-3xl) var(--space-lg);
  flex-direction: column;
  gap: var(--space-sm);
}

.nav-mobile-overlay.open {
  display: flex;
}

.nav-mobile-overlay .nav-item {
  font-size: var(--font-size-lg);
  color: var(--color-white);
  padding: var(--space-md);
}

.nav-mobile-overlay .nav-item.active {
  color: var(--color-accent-light);
}

.nav-mobile-close {
  position: absolute;
  top: 24px;
  right: 24px;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: none;
  background: rgba(255, 255, 255, 0.1);
  color: var(--color-white);
  cursor: pointer;
  font-size: 24px;
}

@media (max-width: 1023px) {
  .nav-links {
    display: none;
  }
  .nav-mobile-toggle {
    display: flex;
  }
  .nav-pill-container {
    width: calc(100% - 48px);
  }
}

@media (max-width: 767px) {
  .nav-pill-container {
    top: 16px;
    width: calc(100% - 32px);
  }
  .nav-pill {
    padding: var(--space-sm) var(--space-md);
  }
}

/* ============================================
   5. Page Headers
   ============================================ */
.page-header {
  margin-bottom: var(--space-xl);
  padding-top: 80px; /* Account for fixed nav */
}

.page-title {
  font-size: var(--font-size-2xl);
  font-weight: 600;
  color: var(--color-text-primary);
  letter-spacing: -0.02em;
  margin-bottom: var(--space-xs);
}

.page-subtitle {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

/* ============================================
   6. Cards
   ============================================ */
.mc-card {
  background: var(--color-canvas-lifted);
  border-radius: var(--radius-card);
  padding: var(--space-lg);
  box-shadow: var(--shadow-card);
  transition: all var(--transition-normal);
}

.mc-card:hover {
  box-shadow: var(--shadow-hover);
}

.mc-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-md);
}

.mc-card-title {
  font-size: var(--font-size-md);
  font-weight: 600;
  color: var(--color-text-primary);
}

.mc-card-sm {
  padding: var(--space-md);
  border-radius: var(--radius-btn);
}

/* ============================================
   7. Stat Cards
   ============================================ */
.stat-card {
  background: var(--color-canvas-lifted);
  border-radius: var(--radius-btn);
  padding: var(--space-lg);
  text-align: center;
}

.stat-value {
  font-size: var(--font-size-3xl);
  font-weight: 700;
  color: var(--color-text-primary);
  letter-spacing: -0.03em;
  line-height: 1.1;
}

.stat-label {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-top: var(--space-xs);
}

/* ============================================
   8. Buttons
   ============================================ */
.mc-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-lg);
  font-family: var(--font-family);
  font-size: var(--font-size-sm);
  font-weight: 500;
  letter-spacing: -0.02em;
  border-radius: var(--radius-btn);
  border: 1.5px solid transparent;
  cursor: pointer;
  transition: all var(--transition-fast);
  line-height: 1.5;
}

.mc-btn-primary {
  background: var(--color-ink);
  color: var(--color-canvas);
  border-color: var(--color-ink);
}

.mc-btn-primary:hover {
  opacity: 0.9;
}

.mc-btn-secondary {
  background: var(--color-white);
  color: var(--color-ink);
  border-color: var(--color-ink);
}

.mc-btn-secondary:hover {
  background: var(--color-canvas);
}

.mc-btn-ghost {
  background: transparent;
  color: var(--color-ink);
  border-color: transparent;
}

.mc-btn-ghost:hover {
  background: rgba(0, 0, 0, 0.04);
}

.mc-btn-sm {
  padding: var(--space-xs) var(--space-md);
  font-size: var(--font-size-xs);
}

.mc-btn-lg {
  padding: var(--space-md) var(--space-xl);
  font-size: var(--font-size-base);
  border-radius: var(--radius-lg);
}

/* ============================================
   9. Tables
   ============================================ */
.mc-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--color-canvas-lifted);
  border-radius: var(--radius-card);
  overflow: hidden;
}

.mc-table th {
  text-align: left;
  padding: var(--space-md) var(--space-lg);
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  background: var(--color-canvas);
  border-bottom: 1px solid var(--color-border);
}

.mc-table td {
  padding: var(--space-md) var(--space-lg);
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  border-bottom: 1px solid var(--color-border);
}

.mc-table tr:last-child td {
  border-bottom: none;
}

.mc-table tbody tr {
  transition: all var(--transition-fast);
}

.mc-table tbody tr:hover td {
  background: var(--color-canvas);
}

/* ============================================
   10. Price & Badge Styles
   ============================================ */
.price-up {
  color: var(--color-up);
}

.price-down {
  color: var(--color-down);
}

.price-flat {
  color: var(--color-flat);
}

.mc-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px var(--space-sm);
  font-size: var(--font-size-xs);
  font-weight: 500;
  border-radius: var(--radius-pill);
}

.mc-badge-up {
  background: var(--color-danger-light);
  color: var(--color-up);
}

.mc-badge-down {
  background: var(--color-success-light);
  color: var(--color-down);
}

.mc-badge-flat {
  background: rgba(134, 134, 139, 0.1);
  color: var(--color-flat);
}

/* ============================================
   11. Grid System
   ============================================ */
.mc-grid {
  display: grid;
  gap: var(--space-lg);
}

.mc-grid-2 {
  grid-template-columns: repeat(2, 1fr);
}

.mc-grid-3 {
  grid-template-columns: repeat(3, 1fr);
}

.mc-grid-4 {
  grid-template-columns: repeat(4, 1fr);
}

@media (max-width: 1023px) {
  .mc-grid-3,
  .mc-grid-4 {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 767px) {
  .mc-grid-2,
  .mc-grid-3,
  .mc-grid-4 {
    grid-template-columns: 1fr;
  }
}

/* ============================================
   12. Utilities
   ============================================ */
.flex {
  display: flex;
}

.flex-between {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.flex-center {
  display: flex;
  justify-content: center;
  align-items: center;
}

.flex-col {
  flex-direction: column;
}

.gap-sm { gap: var(--space-sm); }
.gap-md { gap: var(--space-md); }
.gap-lg { gap: var(--space-lg); }

.mt-sm { margin-top: var(--space-sm); }
.mt-md { margin-top: var(--space-md); }
.mt-lg { margin-top: var(--space-lg); }
.mb-sm { margin-bottom: var(--space-sm); }
.mb-md { margin-bottom: var(--space-md); }
.mb-lg { margin-bottom: var(--space-lg); }

/* ============================================
   13. Loading & Empty States
   ============================================ */
.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
}

.empty-state {
  text-align: center;
  padding: var(--space-2xl);
  color: var(--color-text-secondary);
}

/* ============================================
   14. Animations
   ============================================ */
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.fade-in {
  animation: fadeIn 0.4s ease forwards;
}

/* ============================================
   15. Ant Design Overrides
   ============================================ */

/* Cards */
.ant-card {
  border-radius: var(--radius-card) !important;
  border: none !important;
  background: var(--color-canvas-lifted) !important;
  box-shadow: var(--shadow-card) !important;
}

.ant-card:hover {
  box-shadow: var(--shadow-hover) !important;
}

.ant-card-head {
  border-bottom: 1px solid var(--color-border) !important;
}

.ant-card-body {
  padding: var(--space-lg) !important;
}

/* Buttons */
.ant-btn-primary {
  background: var(--color-ink) !important;
  border-color: var(--color-ink) !important;
  border-radius: var(--radius-btn) !important;
  font-weight: 500 !important;
  font-family: var(--font-family) !important;
  letter-spacing: -0.02em !important;
}

.ant-btn-primary:hover {
  opacity: 0.9 !important;
}

.ant-btn-default {
  border-radius: var(--radius-btn) !important;
  border-color: var(--color-ink) !important;
  color: var(--color-ink) !important;
  font-family: var(--font-family) !important;
}

.ant-btn-default:hover {
  background: var(--color-canvas) !important;
  border-color: var(--color-ink) !important;
  color: var(--color-ink) !important;
}

.ant-btn {
  border-radius: var(--radius-btn) !important;
  font-family: var(--font-family) !important;
}

/* Inputs */
.ant-input,
.ant-input-affix-wrapper,
.ant-select-selector {
  border-radius: var(--radius-btn) !important;
  border-color: rgba(20, 20, 19, 0.3) !important;
  font-family: var(--font-family) !important;
}

.ant-input:hover,
.ant-input-affix-wrapper:hover,
.ant-select-selector:hover {
  border-color: var(--color-ink) !important;
}

.ant-input:focus,
.ant-input-affix-wrapper-focused {
  border-color: var(--color-ink) !important;
  box-shadow: 0 0 0 2px rgba(20, 20, 19, 0.1) !important;
}

.ant-select-focused .ant-select-selector {
  border-color: var(--color-ink) !important;
  box-shadow: 0 0 0 2px rgba(20, 20, 19, 0.1) !important;
}

/* Select Dropdown */
.ant-select-dropdown {
  border-radius: var(--radius-card) !important;
  overflow: hidden;
}

.ant-select-item {
  font-family: var(--font-family) !important;
}

/* Tables */
.ant-table {
  background: transparent !important;
}

.ant-table-container {
  border-radius: var(--radius-card) !important;
  overflow: hidden !important;
}

.ant-table-thead > tr > th {
  background: var(--color-canvas) !important;
  border-bottom: 1px solid var(--color-border) !important;
  font-size: var(--font-size-xs) !important;
  font-weight: 600 !important;
  color: var(--color-text-secondary) !important;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-family: var(--font-family) !important;
}

.ant-table-tbody > tr > td {
  border-bottom: 1px solid var(--color-border) !important;
  font-family: var(--font-family) !important;
}

.ant-table-tbody > tr:hover > td {
  background: var(--color-canvas) !important;
}

.ant-table-row:last-child > td {
  border-bottom: none !important;
}

/* Modal */
.ant-modal-content {
  border-radius: var(--radius-card) !important;
  background: var(--color-canvas-lifted) !important;
  overflow: hidden;
}

.ant-modal-header {
  border-radius: var(--radius-card) var(--radius-card) 0 0 !important;
  background: var(--color-canvas-lifted) !important;
}

.ant-modal-footer {
  border-top: 1px solid var(--color-border) !important;
}

/* Progress */
.ant-progress-inner {
  border-radius: var(--radius-pill) !important;
  background: var(--color-canvas) !important;
}

.ant-progress-bg {
  background: var(--color-ink) !important;
}

/* Tabs */
.ant-tabs-nav {
  font-family: var(--font-family) !important;
}

.ant-tabs-tab {
  font-family: var(--font-family) !important;
  font-weight: 500 !important;
}

.ant-tabs-tab-active .ant-tabs-tab-btn {
  color: var(--color-ink) !important;
}

.ant-tabs-ink-bar {
  background: var(--color-ink) !important;
}

/* Tag */
.ant-tag {
  border-radius: var(--radius-pill) !important;
  font-family: var(--font-family) !important;
  font-weight: 500 !important;
}

/* Pagination */
.ant-pagination-item {
  border-radius: var(--radius-pill) !important;
  font-family: var(--font-family) !important;
}

.ant-pagination-item-active {
  background: var(--color-ink) !important;
  border-color: var(--color-ink) !important;
}

/* Spin */
.ant-spin-dot-item {
  background: var(--color-ink) !important;
}

/* Message */
.ant-message-notice-content {
  border-radius: var(--radius-btn) !important;
  background: var(--color-ink) !important;
  color: var(--color-canvas) !important;
}

/* Tooltip */
.ant-tooltip-inner {
  border-radius: var(--radius-btn) !important;
  font-family: var(--font-family) !important;
}

/* Popover */
.ant-popover-inner {
  border-radius: var(--radius-btn) !important;
}

/* ============================================
   16. Page-Specific Styles
   ============================================ */

/* Dashboard */
.dashboard-index-card {
  background: var(--color-canvas-lifted);
  border-radius: var(--radius-card);
  padding: var(--space-lg);
  cursor: pointer;
  transition: all var(--transition-normal);
}

.dashboard-index-card:hover {
  box-shadow: var(--shadow-hover);
}

.dashboard-chart-container {
  background: var(--color-canvas-lifted);
  border-radius: var(--radius-card);
  padding: var(--space-lg);
}

.dashboard-watchlist-table {
  background: var(--color-canvas-lifted);
  border-radius: var(--radius-card);
  overflow: hidden;
}

/* Agent Analysis */
.agent-stage-card {
  background: var(--color-canvas-lifted);
  border-radius: var(--radius-btn);
  padding: var(--space-md);
  border-left: 3px solid var(--color-border);
  transition: all var(--transition-fast);
}

.agent-stage-card.completed {
  border-left-color: var(--color-success);
}

.agent-stage-card.running {
  border-left-color: var(--color-ink);
}

.agent-stage-card.failed {
  border-left-color: var(--color-danger);
}

.agent-decision-card {
  background: var(--color-canvas-lifted);
  border-radius: var(--radius-card);
  padding: var(--space-xl);
  text-align: center;
}

/* Stock Chart */
.chart-container {
  background: var(--color-canvas-lifted);
  border-radius: var(--radius-card);
  padding: var(--space-lg);
}

.chart-controls {
  display: flex;
  gap: var(--space-sm);
  flex-wrap: wrap;
}

.chart-control-btn {
  padding: var(--space-xs) var(--space-md);
  font-size: var(--font-size-sm);
  font-weight: 500;
  border-radius: var(--radius-btn);
  border: 1px solid var(--color-border-medium);
  background: transparent;
  color: var(--color-ink);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.chart-control-btn:hover {
  background: var(--color-canvas);
}

.chart-control-btn.active {
  background: var(--color-ink);
  color: var(--color-canvas);
  border-color: var(--color-ink);
}

/* Stock List / Screener */
.filter-pill-group {
  display: flex;
  gap: var(--space-sm);
  flex-wrap: wrap;
  margin-bottom: var(--space-md);
}

.filter-pill {
  padding: var(--space-xs) var(--space-md);
  font-size: var(--font-size-sm);
  font-weight: 500;
  border-radius: var(--radius-pill);
  border: 1.5px solid var(--color-border-medium);
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.filter-pill:hover {
  border-color: var(--color-ink);
  color: var(--color-ink);
}

.filter-pill.active {
  background: var(--color-ink);
  color: var(--color-canvas);
  border-color: var(--color-ink);
}

/* Backtest */
.backtest-form-card {
  background: var(--color-canvas-lifted);
  border-radius: var(--radius-card);
  padding: var(--space-xl);
}

.backtest-result-card {
  background: var(--color-canvas-lifted);
  border-radius: var(--radius-card);
  padding: var(--space-lg);
}

/* Strategies */
.strategy-card {
  background: var(--color-canvas-lifted);
  border-radius: var(--radius-card);
  padding: var(--space-xl);
  transition: all var(--transition-normal);
}

.strategy-card:hover {
  box-shadow: var(--shadow-hover);
}

.strategy-icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: var(--color-canvas);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: var(--space-md);
}

/* Responsive */
@media (max-width: 767px) {
  .app-content {
    padding: var(--space-md);
  }

  .page-header {
    padding-top: 72px;
  }

  .mc-card {
    padding: var(--space-md);
    border-radius: var(--radius-btn);
  }
}
```

- [ ] **Step 2: Verify the file was written correctly**

Run: `head -50 frontend/src/index.css`
Expected: Shows the font import and CSS custom properties

- [ ] **Step 3: Commit**

```bash
git add frontend/src/index.css
git commit -m "feat(frontend): implement Mastercard-inspired design system

- Warm cream canvas (#F3F0EE) replaces white backgrounds
- Ink Black (#141413) primary CTAs with 20px pill radius
- Sofia Sans font family from Google Fonts
- Floating pill navigation with 24px top offset
- CSS custom properties for all design tokens
- Ant Design component overrides
- Card, button, table, and badge component classes
- Responsive breakpoints for mobile/tablet/desktop

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 2: Floating Pill Navigation - App.tsx

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Rewrite App.tsx with floating pill navigation**

```tsx
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom'
import { useState } from 'react'
import { SearchOutlined, MenuOutlined, CloseOutlined } from '@ant-design/icons'

import Dashboard from './pages/Dashboard'
import StockList from './pages/StockList'
import StockChart from './pages/StockChart'
import Backtest from './pages/Backtest'
import BacktestHistory from './pages/BacktestHistory'
import Strategies from './pages/Strategies'
import AgentAnalysis from './pages/AgentAnalysis'
import DLPrediction from './pages/DLPrediction'
import Watchlist from './pages/Watchlist'
import Screener from './pages/Screener'

const navItems = [
  { key: '/', label: '仪表盘' },
  { key: '/stocks', label: '股票管理' },
  { key: '/watchlist', label: '自选股' },
  { key: '/screener', label: '股票筛选' },
  { key: '/strategies', label: '策略研究' },
  { key: '/dl-prediction', label: 'DL预测' },
  { key: '/backtest', label: '回测执行' },
  { key: '/history', label: '回测历史' },
  { key: '/agent', label: 'AI分析' }
]

function App() {
  const location = useLocation()
  const navigate = useNavigate()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const isActive = (path: string) => {
    if (path === '/') {
      return location.pathname === '/'
    }
    return location.pathname.startsWith(path)
  }

  return (
    <div className="app-layout">
      {/* Floating Pill Navigation */}
      <div className="nav-pill-container">
        <nav className="nav-pill">
          <div className="nav-logo" onClick={() => navigate('/')}>
            量化系统
          </div>

          {/* Desktop Navigation */}
          <div className="nav-links">
            {navItems.map(item => (
              <div
                key={item.key}
                className={`nav-item ${isActive(item.key) ? 'active' : ''}`}
                onClick={() => navigate(item.key)}
              >
                {item.label}
              </div>
            ))}
          </div>

          {/* Search Button */}
          <button className="nav-search-btn" aria-label="搜索">
            <SearchOutlined />
          </button>

          {/* Mobile Menu Toggle */}
          <button
            className="nav-mobile-toggle"
            onClick={() => setMobileMenuOpen(true)}
            aria-label="打开菜单"
          >
            <MenuOutlined />
          </button>
        </nav>
      </div>

      {/* Mobile Overlay Menu */}
      <div className={`nav-mobile-overlay ${mobileMenuOpen ? 'open' : ''}`}>
        <button
          className="nav-mobile-close"
          onClick={() => setMobileMenuOpen(false)}
          aria-label="关闭菜单"
        >
          <CloseOutlined />
        </button>
        {navItems.map(item => (
          <div
            key={item.key}
            className={`nav-item ${isActive(item.key) ? 'active' : ''}`}
            onClick={() => {
              navigate(item.key)
              setMobileMenuOpen(false)
            }}
          >
            {item.label}
          </div>
        ))}
      </div>

      {/* Main Content */}
      <main className="app-content">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/stocks" element={<StockList />} />
          <Route path="/stocks/:code" element={<StockChart />} />
          <Route path="/watchlist" element={<Watchlist />} />
          <Route path="/screener" element={<Screener />} />
          <Route path="/strategies" element={<Strategies />} />
          <Route path="/dl-prediction" element={<DLPrediction />} />
          <Route path="/backtest" element={<Backtest />} />
          <Route path="/history" element={<BacktestHistory />} />
          <Route path="/agent" element={<AgentAnalysis />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
```

- [ ] **Step 2: Verify the build still works**

Run: `cd frontend && npm run build 2>&1 | head -30`
Expected: Build starts without errors (warnings OK)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat(frontend): implement floating pill navigation

- White pill container fixed 24px from viewport top
- Desktop: horizontal nav links centered with active orange dot indicator
- Mobile: hamburger menu with full-screen overlay
- Search icon button on right side
- Backdrop blur removed for cleaner Mastercard aesthetic

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 3: Dashboard Redesign

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx`

- [ ] **Step 1: Update Dashboard with new card classes**

Replace the Dashboard content with these changes:
1. Change `.apple-card` → `.mc-card` (or inline styles with `border-radius: 40px`)
2. Change `.apple-card-title` → `.mc-card-title`
3. Change `.apple-table` → `.mc-table` (in WatchlistTable)
4. Change `.price-badge.up` → `.mc-badge.mc-badge-up`
5. Change `.price-badge.down` → `.mc-badge.mc-badge-down`
6. Change `.stat-card` → keep but ensure `border-radius: var(--radius-btn)`

Key CSS class replacements:
- `.apple-card` → `border-radius: 40px; background: var(--color-canvas-lifted)`
- `.apple-table` → `border-radius: 40px; overflow: hidden`
- `.stat-card` → `border-radius: 20px`

**Specific changes needed in Dashboard.tsx:**

Line 78-82: IndexCard div
```tsx
// Change: style={{ borderRadius: 'var(--radius-lg)' }}
// To: style={{ borderRadius: 'var(--radius-card)', background: 'var(--color-canvas-lifted)' }}
```

Line 158-209: WatchlistTable
```tsx
// Change: <div className="apple-card">
// To: <div style={{ background: 'var(--color-canvas-lifted)', borderRadius: 'var(--radius-card)', overflow: 'hidden' }}>
```

- [ ] **Step 2: Test Dashboard renders correctly**

Run: `cd frontend && npm run dev` (in background)
Open browser to check: Cards have 40px radius, cream background, Ink Black text

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Dashboard.tsx
git commit -m "feat(frontend): update Dashboard with Mastercard styling

- Cards use 40px radius with cream-lifted background
- Tables use mc-card styling with overflow hidden
- Stat cards use 20px radius
- Index cards styled as large stadium-radius cards
- Market stats use colored values (red/green)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 4: AgentAnalysis Page

**Files:**
- Modify: `frontend/src/pages/AgentAnalysis.tsx`

- [ ] **Step 1: Update AgentAnalysis with new component classes**

Key changes:
1. Replace Ant Design `<Card>` with div + className `mc-card` where appropriate
2. Replace `.apple-btn` → `.mc-btn .mc-btn-primary`
3. Replace progress bar custom styling with Ant Design progress (already styled via CSS override)
4. Decision card: large 40px radius with prominent signal display

**Specific replacements:**
- Line ~463: Analysis form Card → div with `mc-card` styling
- Line ~544: Decision Card → div with `border-radius: 40px`
- Line ~591: Stage cards → use `agent-stage-card` classes
- Line ~646: Loading progress card → `mc-card` with `border-radius: 40px`

- [ ] **Step 2: Verify AgentAnalysis renders**

Run dev server and check: Page loads, tabs work, form styling matches design

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/AgentAnalysis.tsx
git commit -m "feat(frontend): update AgentAnalysis with Mastercard styling

- Analysis form uses mc-card styling
- Stage cards use agent-stage-card with left border indicators
- Decision card prominently styled with 40px radius
- Progress indicators use ink-colored bars
- CTAs use mc-btn-primary (Ink Black pills)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 5: StockList Page

**Files:**
- Modify: `frontend/src/pages/StockList.tsx`

- [ ] **Step 1: Update StockList styling**

Key changes:
- Table container: wrap in div with `border-radius: 40px; overflow: hidden`
- Use `mc-table` class on tables
- Any filter pills: use `.filter-pill` class

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/StockList.tsx
git commit -m "feat(frontend): update StockList with Mastercard styling

- Table container with 40px radius
- mc-table class for consistent table styling
- Filter pills use filter-pill class

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 6: Screener Page

**Files:**
- Modify: `frontend/src/pages/Screener.tsx`

- [ ] **Step 1: Update Screener styling**

Key changes:
- Filter section: use `filter-pill-group` for filter buttons
- Table container: 40px radius
- Use `mc-table` class

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/Screener.tsx
git commit -m "feat(frontend): update Screener with Mastercard styling

- Filter pills use filter-pill group
- Table container with 40px radius
- Consistent with StockList styling

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 7: Watchlist Page

**Files:**
- Modify: `frontend/src/pages/Watchlist.tsx`

- [ ] **Step 1: Update Watchlist styling**

Key changes:
- Table container: 40px radius
- Use `mc-table` class
- Add button: `.mc-btn .mc-btn-primary`

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/Watchlist.tsx
git commit -m "feat(frontend): update Watchlist with Mastercard styling

- Table container with 40px radius
- mc-table class
- Buttons use mc-btn-primary

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 8: StockChart Page

**Files:**
- Modify: `frontend/src/pages/StockChart.tsx`

- [ ] **Step 1: Update StockChart styling**

Key changes:
- Chart container: 40px radius, `border-radius: var(--radius-card)`
- Control buttons: use `.chart-control-btn` class
- Sidebar cards: `mc-card` with 40px radius

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/StockChart.tsx
git commit -m "feat(frontend): update StockChart with Mastercard styling

- Chart area uses 40px radius card
- Control buttons use chart-control-btn class
- Sidebar panels use mc-card styling

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 9: Backtest Page

**Files:**
- Modify: `frontend/src/pages/Backtest.tsx`

- [ ] **Step 1: Update Backtest styling**

Key changes:
- Form sections: `backtest-form-card` styling
- Parameter cards: 40px radius
- Result cards: `backtest-result-card`
- Primary CTA: `.mc-btn .mc-btn-primary`

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/Backtest.tsx
git commit -m "feat(frontend): update Backtest with Mastercard styling

- Form sections use backtest-form-card styling
- Result cards use backtest-result-card
- Primary CTA uses Ink Black pill button

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 10: BacktestHistory Page

**Files:**
- Modify: `frontend/src/pages/BacktestHistory.tsx`

- [ ] **Step 1: Update BacktestHistory styling**

Key changes:
- Table container: 40px radius
- Use `mc-table` class

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/BacktestHistory.tsx
git commit -m "feat(frontend): update BacktestHistory with Mastercard styling

- Table container with 40px radius
- mc-table class for consistent styling

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 11: Strategies Page

**Files:**
- Modify: `frontend/src/pages/Strategies.tsx`

- [ ] **Step 1: Update Strategies styling**

Key changes:
- Strategy cards: `strategy-card` with 40px radius
- Primary CTA: `.mc-btn .mc-btn-primary`
- Secondary buttons: `.mc-btn .mc-btn-secondary`

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/Strategies.tsx
git commit -m "feat(frontend): update Strategies with Mastercard styling

- Strategy cards use strategy-card with 40px radius
- Primary CTAs use Ink Black pill buttons
- Hover states use shadow-card

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 12: DLPrediction Page

**Files:**
- Modify: `frontend/src/pages/DLPrediction.tsx`

- [ ] **Step 1: Update DLPrediction styling**

Key changes:
- Card containers: 40px radius
- Buttons: `.mc-btn .mc-btn-primary`
- Tables: `mc-table` if present

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/DLPrediction.tsx
git commit -m "feat(frontend): update DLPrediction with Mastercard styling

- Cards use 40px radius
- Buttons use mc-btn-primary
- Consistent with other pages

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 13: StockSearch Component

**Files:**
- Modify: `frontend/src/components/StockSearch.tsx`

- [ ] **Step 1: Update StockSearch styling**

Key changes:
- Select component: ensure pill-style via Ant Design overrides
- No additional CSS needed - Ant Design overrides handle the styling

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/StockSearch.tsx
git commit -m "feat(frontend): StockSearch uses Ant Design pill styling

- No additional changes needed - inherits from index.css overrides
- Select uses 20px border-radius via Ant Design overrides

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 14: Final Verification

- [ ] **Step 1: Run full build**

Run: `cd frontend && npm run build`
Expected: Clean build with no errors

- [ ] **Step 2: Test in browser**

Run: `npm run dev`
Open all pages and verify:
- Navigation pill floats 24px from top
- All cards have 40px radius (large) or 20px (small)
- Buttons are Ink Black pills
- Tables have proper header styling
- No blue (#0071e3) anywhere

- [ ] **Step 3: Commit verification**

```bash
git add -A
git commit -m "chore(frontend): complete Mastercard-inspired redesign

All pages updated with new design system:
- Warm cream canvas backgrounds
- Floating pill navigation
- 40px/20px radius on containers/buttons
- Ink Black CTAs
- Sofia Sans typography
- Consistent component styling across all pages

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Self-Review Checklist

After completing all tasks, verify:

1. **Spec coverage**: All design tokens from spec are implemented in index.css
2. **Placeholder scan**: No "TBD", "TODO", or placeholder content
3. **Type consistency**: All class names are consistent across files
4. **Cross-reference check**: All pages use the same `.mc-card`, `.mc-btn-primary` patterns
5. **Build verification**: `npm run build` succeeds

---

## Plan Summary

| Task | File | Changes |
|------|------|---------|
| 1 | index.css | Full design system CSS |
| 2 | App.tsx | Floating pill navigation |
| 3 | Dashboard.tsx | Card/table styling |
| 4 | AgentAnalysis.tsx | Cards/buttons/stages |
| 5 | StockList.tsx | Table styling |
| 6 | Screener.tsx | Filter pills/table |
| 7 | Watchlist.tsx | Table styling |
| 8 | StockChart.tsx | Chart/controls styling |
| 9 | Backtest.tsx | Form/result cards |
| 10 | BacktestHistory.tsx | Table styling |
| 11 | Strategies.tsx | Strategy cards |
| 12 | DLPrediction.tsx | Card styling |
| 13 | StockSearch.tsx | Select styling |
| 14 | Final | Build verification |

**Estimated tasks: 14**
**Estimated commits: 14**
