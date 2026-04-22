# Smooth Scroll Runbook

Last updated: 2026-04-21 23:17:03 +09:00

## Goal
- Keep anchor navigation (`#...`) smooth and stable across generated LP pages.
- Avoid repeating the same trial-and-error fixes.

## Current Standard
- Keep CSS smooth scroll enabled:
  - `html { scroll-behavior: smooth; scroll-padding-top: 80px; }`
  - `body { overflow-x: hidden; scroll-behavior: smooth; scroll-padding-top: 80px; }`
- Use JS supplement in `script.js` for anchor formats beyond `#...`:
  - `#about`
  - `index.html#about`
  - `/index.html#about`
- Apply navbar offset when scrolling (`navbar.offsetHeight + 8`).

## Implementation History (timestamped)
- 2026-04-21 23:17:03 +09:00
  - Test result: success.
  - Symptom resolved: smooth scroll now works.
  - Verified path: navbar anchor click (same-page section jump).
- 2026-04-21 23:09:35 +09:00
  - New action (non-duplicate): replaced native `behavior: "smooth"` calls with `requestAnimationFrame` custom scroll animation.
  - Reason: native smooth scrolling can be ignored by environment/browser settings even when click interception works.
  - Files: `script.js`.
- 2026-04-21 23:06:34 +09:00
  - Test result: failed.
  - Symptom: smooth scroll did not work at all.
  - Status: unresolved, needs runtime-level investigation (actual click event path + computed scroll container).
- 2026-04-21 23:01:02 +09:00
  - Added robust same-page anchor handling in `script.js` using `URL(...)`.
  - Ensured smooth scroll works for hash links with or without path prefix.
  - Preserved external/other-page link behavior.

## Do Not Repeat
- Do not re-add/remove anchor interception blindly.
- Do not assume only `href^="#"]` exists; generated HTML may include `index.html#...`.
- Do not patch before checking actual rendered `href` format in DevTools.

## One-pass Verification Checklist
1. Open generated page and inspect one navbar link `href`.
2. Confirm target element with matching `id` exists.
3. Click link and verify:
   - smooth movement occurs
   - top offset respects fixed navbar
   - URL hash updates
4. Repeat once for drawer link (mobile).

## If It Breaks Again
- First compare failing link format (`#...` vs `index.html#...`).
- Then inspect console errors from `script.js`.
- Update this file with a new timestamped entry before changing logic.
