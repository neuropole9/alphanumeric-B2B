# Release 5.0.5 Project Book QA

- Sanitized sample project: Skyline Towers - Tower A and Tower B
- Application: LIGHTING
- Rooms expected/rendered: 16 / 16
- Configured room placements expected/rendered: 19 / 19
- Unique products expected/rendered: 4 / 4
- Quantity expected/reconciled: 119 / 119
- Project Book pages: 29
- Building Book pages: 23
- Floor Sheet pages: 1
- Room Sheet pages: 3
- Image mapping: SKU-LP-24W-001 -> `fixtures/products/led-panel-front.png`; SKU-DL-12W-002 -> `fixtures/products/led-downlight-primary.png`
- Primary-image switching: verified by changing the LED panel primary row, regenerating, and asserting different Project Book bytes plus the selected storage key.
- Aspect ratio: both 1200x900 PNG fixtures are rendered with ReportLab `kind=proportional`.
- Missing-image fallback: SKU-TL-20W-003 intentionally has no media and renders `Image unavailable`/`Unavailable` without aborting.
- Specification order: {'SKU-LP-24W-001': ['Power', 'Voltage', 'Frequency', 'Lumens', 'Color Temperature', 'Cri', 'Power Factor', 'Ip Rating', 'Dimensions', 'Warranty'], 'SKU-DL-12W-002': ['Power', 'Voltage', 'Lumens', 'Color Temperature', 'Ip Rating'], 'SKU-TL-20W-003': ['Power', 'Mounting', 'Voltage']}
- Preview/download equivalence: both routes use the same backend report service and the generated response bytes are the packaged sample bytes.
- Quantity reconciliation: RoomProduct rows -> room schedules -> aggregate BOQ -> unique product sheets totals checked at 119.
- Visual page inspection: PASS — all generated Project Book, Building Book, Floor Sheet, Room Sheet, and invoice pages were rendered with Poppler; no clipping, overlap, distorted images, broken headers, or unexpected blank pages were found.
