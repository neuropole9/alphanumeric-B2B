# UI audit

## Navigation

Admin navigation is limited to Dashboard, Customers, Product Catalogue, Settings and Audit Log. Customer users see My Project, Product Catalogue and Profile. Projects, buildings, rooms, users and commercial records are reached contextually.

## Interaction model

- Breadcrumbs preserve Customer → Project → Building → Floor → Room context.
- Product choice is two-stage: select a family, then review an exact variant.
- Room selection asks “Does this product suit this room?” before any mutation.
- Yes approves and upserts the variant; No leaves the room unchanged and retains the rejected proposal for Admin review.
- Product cards and detail galleries use authenticated uploaded or seeded media with a resilient fallback.

## Accessibility and responsiveness

- Dialogs trap focus, close with Escape and restore focus to their trigger.
- Controls have explicit button semantics and keyboard-accessible navigation.
- Tables scroll safely; grids collapse across laptop, tablet and mobile breakpoints.
- Route-level code splitting keeps first-load assets bounded.
