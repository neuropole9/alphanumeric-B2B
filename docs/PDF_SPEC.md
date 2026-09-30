# PDF and workbook specification

## Project and building books

- A4 pages with branded cover, running header, footer and page number.
- Customer, partner and inquiry context; building, floor and room summaries; main boards; room product schedules; BOQ and commercial history.
- Project books include every building. Building books contain only the selected building.
- Prices are present for authorized Admin users and omitted from customer-user output.

## Room sheet

- A4 room identity, building/floor context and approved exact product variants with quantities.

## Building BOQ workbook

- `Building BOQ`: grouped exact variants, typed numeric values, quantities, units and role-aware pricing.
- `Room Breakdown`: exact allocation by floor and room.
- Both sheets use frozen headers, filters, print settings, readable widths and restrained brand styling.

Every report is generated server-side from current scoped database records. The delivery gate renders all PDF pages and both workbook sheets for visual inspection.
