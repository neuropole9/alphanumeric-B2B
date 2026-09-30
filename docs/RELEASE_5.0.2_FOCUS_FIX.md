# AlphaNumeric B2B Release 5.0.2 — Product Form Focus Fix

## Status

The release-blocking one-character typing defect is fixed and covered by automated regression tests. Frontend tests, production build, backend tests, dependency audit, fresh migration, and Release 5 database preflight pass.

Manual Chrome viewport validation is not claimed: the available browser environment blocked access to the local validation server with `ERR_BLOCKED_BY_CLIENT`. Run the checklist below on a workstation before production promotion.

## Root cause

`Modal` received inline `onClose` callbacks from product and other form pages. Its focus-management effect depended on the callback identity. Every controlled-input update rerendered the parent and created a new callback, so the effect cleaned up and ran again after every keystroke. The effect then focused the modal's first focusable control. The typed field therefore accepted the first character and immediately lost focus.

This was a shared modal defect affecting Add Product Family, Add/Edit Variant, dynamic specifications, pricing, descriptions, image metadata, stock, project access/customer invitation, and other modal forms.

## Fix

- Store the latest close callback in a stable ref.
- Run focus initialization and keyboard-listener setup only when modal open state changes.
- Preserve current focus during ordinary parent rerenders.
- Keep Escape handling connected to the latest close callback without restarting focus management.
- Add realistic `userEvent` coverage for continuous typing and editing behavior.

No auto-refocus workaround was added.

## Changed files

- `frontend/src/components/UI.tsx`
- `frontend/src/components/UI.focus.test.tsx`
- `frontend/package.json`
- `frontend/package-lock.json`
- `backend/app/main.py`
- `docs/RELEASE_5.0.2_FOCUS_FIX.md`

## Regression evidence

Before the fix, the regression test typed `COB Luminaire` but the input contained only `C`.

After the fix, the suite verifies:

- Product and family names
- Short and full descriptions
- Dynamic text specifications
- Numeric pricing
- Repeatable feature rows after add and reorder
- Image alternative text
- Existing Edit Product data preservation
- Debounced autosave behavior without stale state replacement
- Typing after inline category creation and selection
- Rapid typing, spaces, punctuation, Backspace, cursor insertion, paste, Tab and Shift+Tab
- Mobile-width execution
- Active-field focus and no component remount

## Executed gates

- Frontend: 35 tests passed, including 13 focus regressions
- Frontend TypeScript and Vite production build: passed
- Production npm audit: 0 vulnerabilities
- Backend: 26 tests passed
- Fresh SQLite migration: `0009 (head)`
- Release 5 preflight: pass, 0 issues

## Manual workstation checklist

Run the backend and frontend, sign in as an administrator, and check Add Product Family, Add Variant, Edit Variant, Edit Family, image upload metadata, stock adjustment, project access/customer invitation, search, and filter controls at widths 1440, 1280, 768, and 390 pixels.

For each applicable text field, enter at least 30 continuous characters and confirm focus and cursor stability, no flicker, no console errors or React key warnings, no per-character API requests, no reset of unrelated values, and correct persistence after save and reopen.

Do not promote to production until this checklist passes in Chrome against the intended deployment environment.
