# Welcome Editorial Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Apply approved prototype A to the full Backing welcome page.

**Architecture:** Keep the static HTML/CSS/JS welcome page and existing login routes. Use the approved split hero, warm white, orange, Geist with Chinese fallback, and varied editorial sections. No new runtime dependencies or public data APIs.

**Tech Stack:** HTML, CSS, JavaScript, Vite, Playwright.

**Spec:** User-approved A prototype at `.superpowers/brainstorm/1115-1793427331/content/hero-a.html`; conversation decisions: evaluator audience, quantitative researchers, Backing 量化系统, 13-strategy public directory, trust section.

## Global Constraints

- Preserve `/welcome/`, `/login`, safe `next` propagation, legal links and accessible mobile menu.
- Main headline: 让策略，经得起回测。 Primary action: 进入研究工作台.
- Follow landing-page-design for type scale, spacing, heading text gradient, floating navigation and reduced motion.
- Preserve truthful product claims; never promise prevention of all hallucinations or lookahead errors.
- No fabricated testimonials or returns. Public strategy directory is a static snapshot of the 13 built-ins, not an unauthenticated API call.
- Limit production edits to welcome files, welcome images and existing landing E2E tests. Preserve unrelated working changes. No commits requested.

## Review Focus

- JavaScript unavailable: all content and native FAQ remain visible.
- Redirect input: external and protocol-relative destinations must not propagate.
- Mobile navigation: keyboard focus, Escape and scroll restoration work.
- Narrow viewports: no horizontal scroll and headings remain readable.
- Reduced motion: all content visible without movement.

### Task 1: Editorial page

**Files:** `frontend/public/welcome/index.html`, `landing.css`.
**Interfaces:** Existing classes/IDs for menu, login links, FAQ and reveals remain compatible with landing.js.

- [x] Update existing E2E expectations for approved headline, CTA and 13 strategies; verify current page fails those expectations.
- [x] Build split hero and proof band from A; add varied benefits, three-stage workflow, strategy directory, product crops, trust statements, 8 FAQ answers, tagline, final CTA and footer.
- [x] Preserve SEO metadata and synchronize FAQ structured data with visible answers; use existing legal-page CSS hooks.

### Task 2: Progressive enhancement

**Files:** `frontend/public/welcome/landing.js`, `frontend/e2e/landing.spec.ts`.
**Interfaces:** `safeNextPath(value)` validates same-origin relative routes. Menu retains focus handling. Strategy filters progressively enhance a visible 13-item list.

- [x] Add meaningful tests for unsafe redirects, strategy category filtering and script-load failure.
- [x] Keep all content visible by default; enable reveals only after observer registration. Animate tagline by segment in reading order.
- [x] Add category filters with `aria-pressed`, default all 13 visible. Keep native FAQ usable without scripts.

### Task 3: Verify final result

**Files:** Existing welcome E2E tests and generated review artifacts only.

- [x] Run landing Playwright suite, frontend build and formatting for changed sources.
- [x] Inspect the full page at desktop, tablet and phone widths, reduced motion and no JavaScript. Verify links, filters and menu.
- [x] Correct visible issues and report actual validation results and any limitations.
