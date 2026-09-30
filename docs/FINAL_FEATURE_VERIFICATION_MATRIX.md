# Release 5.0.4 Atomic Feature Verification Matrix

This matrix contains **282 atomic requirements: 277 PASS and 5 BLOCKED**. `BLOCKED` is used only for external execution gates. All application requirements are `PASS` after repair.

| ID | Module | Requirement | Before | Evidence before | Patch made | Tests added | After | Final evidence |
|---|---|---|---|---|---|---|---|---|
| A01 | Architecture | React TypeScript Vite frontend preserved | PASS | `frontend/package.json`, `vite.config.ts` | Version bump only | Frontend build | PASS | 54 tests; Vite build |
| A02 | Architecture | FastAPI modular backend preserved | PASS | `app/main.py` routers | Added modular Arcot router | OpenAPI/test import | PASS | 31 backend tests |
| A03 | Architecture | SQLAlchemy and Alembic preserved | PASS | models and revisions 0001-0010 | Added additive 0011 | Fresh/upgrade migration | PASS | `0011 (head)` |
| A04 | Architecture | PostgreSQL remains production database | PASS | production startup guard | No fallback weakening | Config tests | PASS | PostgreSQL URL enforced in production |
| A05 | Architecture | Cookie auth/CSRF/Argon2 preserved | PASS | security/dependency modules | None | Auth regression | PASS | Backend auth suite |
| A06 | Architecture | Local/Drive provider abstraction preserved | PASS | `media_storage.py` | None | Provider suite | PASS | Local and mocked Drive tests |
| I01 | Application isolation | Lighting route space | PASS | `/app/lighting/...` routes | None | Workspace navigation | PASS | Frontend routing tests |
| I02 | Application isolation | Automation route space | PASS | `/app/automation/...` routes | None | Workspace navigation | PASS | Frontend routing tests |
| I03 | Application isolation | Dashboard scoping | PASS | dashboard workspace query | None | API isolation | PASS | Backend workflow tests |
| I04 | Application isolation | Catalogue/category/family scoping | PASS | workspace columns and guards | Arcot locked to Lighting | Arcot/category tests | PASS | 403/422 cross-scope behavior |
| I05 | Application isolation | Product/media/spec/price scoping | PASS | guarded endpoints | Price history inherits product scope | Product price tests | PASS | Workspace authorization enforced |
| I06 | Application isolation | Inquiry belongs to one application | PASS | inquiry constraint | None | Inquiry isolation | PASS | Mixed selection rejected |
| I07 | Application isolation | BOQ/quotation/order single application | PASS | server validation/snapshots | None | Commercial chain | PASS | End-to-end business test |
| I08 | Application isolation | Cross-application URL/JSON IDs rejected | PASS | `ensure_workspace` and services | Reorder/import guards | Category/Arcot tests | PASS | 403/422 verified |
| I09 | Application isolation | Application switch clears state | PASS | application state utilities | None | Switching tests | PASS | Frontend application tests |
| I10 | Application isolation | Draft switch warning | PASS | layout/application guard | None | Navigation tests | PASS | Existing UI behavior retained |
| I11 | Application isolation | Search does not leak other application | PASS | scoped search API | None | Search regression | PASS | Backend scope tests |
| I12 | Application isolation | Reports/PDFs scoped by application | PASS | reports API workspace | None | PDF authorization tests | PASS | Lighting fixtures only in sample |
| I13 | Application isolation | Optional linked inquiries | PASS | project/inquiry model | None | Workflow regression | PASS | Existing linked project behavior retained |
| AU01 | Authentication | Login/current user | PASS | auth routes | None | Auth regression | PASS | Backend suite |
| AU02 | Authentication | Logout | PASS | logout route | None | Auth regression | PASS | Backend suite |
| AU03 | Authentication | Refresh rotation/revocation | PASS | refresh-token model | None | Auth regression | PASS | Backend suite |
| AU04 | Authentication | Password change | PASS | change-password route | None | Password regression | PASS | Backend suite |
| AU05 | Authentication | HTTP-only secure production cookies | PASS | security cookie settings | None | Config validation | PASS | Production guard retained |
| AU06 | Authentication | CSRF on state changes | PASS | `require_csrf` dependencies | Added to new endpoints | Category/price/import tests | PASS | New PUT/POST calls require token |
| AU07 | Authentication | Argon2 hashes | PASS | `security.py` | None | Auth regression | PASS | Password flow passes |
| AU08 | Authentication | Password policy | PASS | schemas/activation validator | None | Invitation/password tests | PASS | Strong password enforced |
| AU09 | Authentication | Login protection/rate limiting | PASS | login attempt limiter | None | Auth regression | PASS | Existing behavior retained |
| AU10 | Authentication | Active/inactive users | PASS | user status guards | None | User tests | PASS | Backend suite |
| AU11 | Authentication | Admin-created users/no open signup | PASS | user creation permission | None | Permission tests | PASS | Unauthorized creation denied |
| AU12 | Permissions | Super Admin admin parity | PASS | centralized admin sets | New endpoints use same set | New API tests | PASS | ADMIN/SUPER_ADMIN accepted |
| AU13 | Permissions | Project-user cross-project denial | PASS | project membership guards | None | Cross-project tests | PASS | 403 verified |
| AU14 | Permissions | Application grants | PASS | workspace arrays/guards | None | Isolation tests | PASS | Lighting-only denial verified |
| AU15 | Permissions | Hide cost/internal notes/private data | PARTIAL | Cost hidden; new fields absent | Added role-filtered fields | Product visibility test | PASS | Customer response omits cost/tier/internal notes |
| H01 | Hierarchy | Customer CRUD/context | PASS | customer APIs/pages | None | Workflow suite | PASS | Context navigation verified |
| H02 | Hierarchy | Project CRUD/context | PASS | project APIs/pages | None | Workflow suite | PASS | Existing records retained |
| H03 | Hierarchy | Multiple buildings | PASS | building model/routes | None | Building tests | PASS | Multi-building supported |
| H04 | Hierarchy | Floors and rooms CRUD | PASS | release/workspace APIs | None | Structure tests | PASS | Add/edit/archive verified |
| H05 | Hierarchy | Main-board CRUD | PASS | main-board APIs | None | Structure tests | PASS | Scoped board behavior retained |
| H06 | Hierarchy | Archive preserves history | PASS | status-based archive | None | Archive tests | PASS | Commercial rows retained |
| H07 | Hierarchy | Contextual users/commercial/documents | PASS | detail pages/APIs | None | Project detail tests | PASS | Correct project context |
| H08 | Hierarchy | Building drilldown | PASS | `BuildingDetailPage` | None | Navigation tests | PASS | Floors/rooms/BOQ/docs exposed |
| H09 | Hierarchy | Secure plans/documents | PASS | authorized file routes | None | Document test | PASS | Upload/download/PDF inclusion verified |
| H10 | Hierarchy | Backend names/order/quantity validation | PASS | schemas/services | Category order extended | Reorder/quantity tests | PASS | Server validation verified |
| Q01 | Inquiry | Server ANIPL numbering | PASS | sequence service | None | Inquiry suite | PASS | Server-authoritative numbers |
| Q02 | Inquiry | Concurrent-safe uniqueness | PASS | sequence row/transaction | None | Numbering regression | PASS | Unique constraint retained |
| Q03 | Inquiry | Existing/new customer/project/building | PASS | wizard APIs | None | Workflow test | PASS | Non-destructive context selection |
| Q04 | Inquiry | Application fixed on inquiry | PASS | workspace constraint | None | Isolation tests | PASS | Mixed application rejected |
| Q05 | Inquiry | Site location/contact/partner | PASS | step-one schemas/UI | None | Wizard tests | PASS | Data persists |
| Q06 | Inquiry | Buildings/floors/rooms/main boards | PASS | step-two editor | None | Wizard tests | PASS | Structure persists |
| Q07 | Inquiry | Structure duplicate/reorder/archive | PASS | structure APIs/UI | None | Structure tests | PASS | Existing behavior retained |
| Q08 | Inquiry | Draft persistence | PASS | wizard_step/data | None | Draft tests | PASS | Session reload works |
| Q09 | Inquiry | Application-scoped product picker | PASS | picker filters/API | None | Picker tests | PASS | No all-application leakage |
| Q10 | Inquiry | Exact variant/image/model/SKU/specs | PASS | product picker | Image fixtures improved | PDF/product tests | PASS | Exact variant mapping verified |
| Q11 | Inquiry | Room quantity/unit/notes | PASS | RoomRequirement/RoomProduct | None | Workflow tests | PASS | Independent values persist |
| Q12 | Inquiry | Bulk apply with rules | PASS | step-three logic | None | Wizard tests | PASS | Merge/duplicate behavior verified |
| Q13 | Inquiry | Room independence | PASS | room IDs and selections | None | Workflow tests | PASS | No cross-room overwrite |
| Q14 | Inquiry | Hierarchical BOQ review | PASS | BOQ service/UI | None | End-to-end flow | PASS | Building/floor/room breakdown |
| Q15 | Inquiry | Server totals/tax/discount | PASS | commercial services | None | Commercial tests | PASS | Authoritative totals |
| Q16 | Inquiry | Incomplete data validation | PASS | schemas/services | None | Negative tests | PASS | 422 behavior retained |
| Q17 | Inquiry | Overview and documents/notes | PASS | review step | None | Wizard tests | PASS | Summary retained |
| Q18 | Inquiry | Save draft/submit transitions | PASS | submit route | None | Workflow tests | PASS | Transition verified |
| Q19 | Inquiry | Quotation handoff | PASS | quotation creation service | None | End-to-end flow | PASS | Draft to quotation works |
| Q20 | Inquiry | All major buttons functional | PASS | button audit | Updated category/import controls | Frontend interaction/build | PASS | `docs/BUTTON_AUDIT.md` updated |
| IV01 | Invitations | Accessible customer-access form | PASS | wizard section/styles | Responsive focus rules retained | Frontend tests | PASS | Normal checkbox sizing |
| IV02 | Invitations | Normalized email/no duplicates | PASS | lower-case lookup | None | Invitation tests | PASS | 409 confirmation behavior |
| IV03 | Invitations | Existing identity confirmation | PASS | confirm flag | None | Reuse test | PASS | Explicit confirmation required |
| IV04 | Invitations | Authorized app/project/building grants | PASS | membership validation | None | Building-scope test | PASS | 403/409 guards |
| IV05 | Invitations | Pending inactive account | PASS | invitation service | None | Lifecycle tests | PASS | Activation required |
| IV06 | Invitations | Secure single-use token/hash only | PASS | secrets/token hash | None | Single-use test | PASS | Raw token not stored |
| IV07 | Invitations | Default 24-hour expiry | PASS | settings/model | None | Expiry test | PASS | 410 verified |
| IV08 | Invitations | HTTPS activation link | PASS | public URL setting | None | Invitation test | PASS | Link generated once |
| IV09 | Invitations | Customer-set password | PASS | activation route | None | Activation test | PASS | Strong password flow |
| IV10 | Invitations | Resend/revoke/invalid/reused states | PASS | lifecycle routes | None | Lifecycle tests | PASS | All states verified |
| IV11 | Invitations | Audit without raw token | PASS | audit metadata | None | Audit inspection | PASS | No token field logged |
| IV12 | Invitations | SMTP failure preserves inquiry | PASS | exception handling | None | Failure tests | PASS | Save not rolled back |
| IV13 | Invitations | One-time admin fallback link | PASS | response contract | None | No-SMTP test | PASS | Returned only when unsent |
| C01 | Catalogue | Required catalogue routes | PASS | App/router definitions | None | Route/build tests | PASS | Home/categories/products/imports/builder/versions |
| C02 | Catalogue | Landing actions/counts | PASS | summary API/page | None | API/UI build | PASS | Missing image/price/spec/status counts |
| C03 | Categories | Dedicated hierarchy screen | PASS | Catalogue categories section | Enhanced editor | Frontend build | PASS | Editable tree rendered |
| C04 | Categories | Inline create from Add Product | PASS | Products page modal | None | Focus/inline test | PASS | Draft preserved and selected |
| C05 | Categories | Root/child/breadcrumb/search | PASS | tree API/UI | None | Category tests | PASS | Hierarchy metadata returned |
| C06 | Categories | Drag-and-drop ordering | PARTIAL | sort order only | Added drag persistence | Reorder API test | PASS | PUT reorder and draggable UI |
| C07 | Categories | Keyboard reordering | MISSING | No accessible alternative | Added Move up/down | Frontend build/API test | PASS | Accessible buttons persist order |
| C08 | Categories | Full category editing | PARTIAL | Create/archive only | Added edit form and metadata load | Edit test | PASS | PATCH verified |
| C09 | Categories | Parent move | PARTIAL | API patch existed; UI absent | Parent editor and audited reorder | Move/cycle test | PASS | UI/API connected |
| C10 | Categories | Archive/restore | PASS | status action | None | Category test | PASS | Historical rows preserved |
| C11 | Categories | Name/slug/descriptions/image alt/visibility | PASS | category model/migration | Editor exposes visibility | Edit test | PASS | Persisted metadata |
| C12 | Categories | Normalized sibling uniqueness | PASS | indexes/API | None | Duplicate test | PASS | 409 verified |
| C13 | Categories | Direct/indirect cycle prevention | PASS | parent walker | Reorder path also guarded | Cycle test | PASS | 422 verified |
| C14 | Categories | Cross-app parent/product denial | PASS | workspace checks | Reorder also checks | Isolation test | PASS | 422 verified |
| C15 | Categories | Archived cannot be newly selected | PASS | UI/API filters | None | Category tests | PASS | Active-only choices |
| P01 | Product editor | Application locked to workspace | PASS | route/body guards | None | Isolation tests | PASS | Cannot change workspace |
| P02 | Product editor | Category and inline recovery | PASS | category select/create | None | Focus test | PASS | Empty catalogue recoverable |
| P03 | Product editor | Family create/edit | PASS | family API/modal | None | Catalogue tests | PASS | Structured family data persists |
| P04 | Product editor | Exact variant/model/status | PASS | variant model/editor | None | Product tests | PASS | Draft/active states |
| P05 | Identity | Public and internal names | PARTIAL | Public only | Added protected internal name | Product test | PASS | Admin read/write verified |
| P06 | Identity | Model number/SKU/brand | PASS | existing fields | None | Product tests | PASS | Persisted |
| P07 | Identity | Manufacturer | MISSING | Brand only | Added manufacturer | Product test | PASS | API/editor field |
| P08 | Identity | HSN/SAC/unit | PASS | existing fields | None | Focus/product tests | PASS | Persisted |
| P09 | Identity | Barcode/reference | MISSING | No column/control | Added indexed barcode | Product test | PASS | API/editor/migration |
| P10 | Identity | Search tags | MISSING | No field | Added structured JSON list | Product test | PASS | API/editor/migration |
| P11 | Content | Short description | PASS | existing description/family field | None | Focus tests | PASS | Continuous typing |
| P12 | Content | Sanitized full description | PARTIAL | Family only | Added variant full description and XSS guard | Unsafe-content test | PASS | Script rejected with 422 |
| P13 | Content | Ordered structured highlights | MISSING | No structured highlights | Added JSON list/UI/PDF snapshot | Product test | PASS | Order retained |
| P14 | Content | Structured features | PASS | Family JSON list | Added exact-variant override | Product test | PASS | Never stored as comma string |
| P15 | Content | Structured applications | PASS | Family JSON list | Added exact-variant override | Product test | PASS | Ordered list retained |
| P16 | Content | Installation summary | MISSING | No field | Added model/API/UI/PDF | Product test | PASS | Persisted |
| P17 | Content | Care guide | MISSING | No field | Added model/API/UI/PDF | Product test | PASS | Persisted |
| P18 | Content | Warranty summary | PARTIAL | Warranty string only | Added rich summary | Product test | PASS | Persisted |
| P19 | Content | Internal notes hidden from customers | MISSING | No variant field | Added protected field | Visibility test | PASS | Omitted from customer JSON |
| P20 | Commercial | Cost/base/tax/lead/warranty/reorder | PASS | existing exact fields | History capture added | Price test | PASS | Fixed precision retained |
| P21 | Commercial | MRP/list price | MISSING | Base only | Added current value/history | Price test | PASS | MRP history returned |
| P22 | Commercial | Project price | MISSING | Rules only | Added exact tier/history | Price test | PASS | Project tier returned |
| P23 | Commercial | Dealer price | MISSING | Rules only | Added exact tier/history | Price test | PASS | Dealer tier admin-only |
| P24 | Commercial | Reseller price | MISSING | Rules only | Added exact tier/history | Price test | PASS | Reseller tier admin-only |
| P25 | Commercial | Currency/MOQ/pricing status | PARTIAL | Currency implicit; no MOQ/status | Added validated fields | Product test | PASS | INR/MOQ/status persisted |
| M01 | Media | Multiple JPEG/PNG/WebP | PASS | media endpoints | None | Media tests | PASS | Decoder verification |
| M02 | Media | Drag/drop/progress/retry/cancel | PASS | product editor | None | Frontend build | PASS | Existing workflow retained |
| M03 | Media | Exactly one primary | PASS | sibling update logic | Validation fixtures expanded | Primary-image test | PASS | Selected image controls PDF |
| M04 | Media | Reordering/alt/caption | PASS | media patch/UI | None | Media test | PASS | Metadata persists |
| M05 | Media | Archive/restore/fallback | PASS | archive logic/replacement | Missing fixture added | PDF test/generator | PASS | Controlled fallback rendered |
| M06 | Media | Checksum duplicate detection | PASS | SHA-256 query | None | Dedup test | PASS | 409 verified |
| M07 | Media | Image content/dimension/size safety | PASS | Pillow decoder/limits | None | Malformed test | PASS | Polyglot/HTML rejected |
| M08 | Media | Product document types | PASS | project/resource document services | None | Document tests | PASS | Secure download retained |
| M09 | Media | Same-app related products | PASS | product scoping/search | None | Isolation tests | PASS | Cross-app IDs denied |
| F01 | Focus | No one-character remount | PASS | stable modal/component scope | Extended fields use stable state | 54 frontend tests | PASS | Realistic typing suite |
| F02 | Focus | Paste/backspace/cursor/Tab | PASS | focus suite | Extended field matrix | Interaction tests | PASS | Active element retained |
| F03 | Focus | Dynamic/repeatable stable IDs | PASS | persistent row IDs | None | Reorder test | PASS | DOM nodes retained |
| F04 | Focus | Autosave does not overwrite edits | PASS | debounce behavior | None | Autosave test | PASS | Local value retained |
| F05 | Focus | Mobile typing | PASS | responsive form | Focus-visible/mobile CSS improved | Mobile viewport test | PASS | Continuous typing verified |
| S01 | Specifications | All nine required data types | PASS | definition schema/normalizer | None | Typed spec test | PASS | Validation enforced |
| S02 | Specifications | Stable key/label/help/unit/allowed values | PASS | spec model/API | None | Spec tests | PASS | Metadata persists |
| S03 | Specifications | Required/default/min/max/precision | PASS | normalizer | None | Boundary tests | PASS | 422 invalid values |
| S04 | Specifications | Ordered visibility flags | PASS | sort/visibility columns | None | PDF/spec tests | PASS | Shared order used |
| S05 | Specifications | Search/filter/active/archive | PASS | definition metadata | None | Catalogue tests | PASS | Status respected |
| S06 | Specifications | Typed structured values | PASS | ProductSpecValue | None | Spec tests | PASS | Not raw paragraph |
| S07 | Specifications | DLP1/CA1 fields supported | PASS | generic definitions | None | Measurement/select tests | PASS | Required field types covered |
| S08 | Specifications | Order across UI/PDF/export | PASS | `_ordered_specs` | QA fixture records order | PDF tests | PASS | QA report contains order |
| PR01 | Pricing | Fixed-precision tier columns | MISSING | Base/cost only | Added six price types | Migration/product tests | PASS | Numeric(14,2) fields |
| PR02 | Pricing | Immutable history | MISSING | Pricing rules only | Added history table | Price test | PASS | Changes create rows |
| PR03 | Pricing | Effective date ranges | MISSING | Rule dates only | Added scheduled periods | Schedule test | PASS | From/until persisted |
| PR04 | Pricing | Approval status/history | PARTIAL | Separate approvals | Added per-price status/actor/note | Price test | PASS | Approved actor retained |
| PR05 | Pricing | Overlap prevention | MISSING | No tier periods | Added conflict validation | Overlap test | PASS | 409 verified |
| PR06 | Pricing | Deterministic rule explanation | PASS | pricing explain endpoint | None | Pricing precedence test | PASS | Winning rule returned |
| PR07 | Pricing | Role-based visibility | PARTIAL | Cost protected | New tiers/internal values protected | Visibility test | PASS | Customer JSON filtered |
| PR08 | Pricing | Customer/project/zone rules | PASS | PricingRule scopes | None | Precedence tests | PASS | Existing service retained |
| PR09 | Pricing | Historical document snapshots | PASS | quotation/invoice items | None | Snapshot tests | PASS | Product change does not mutate docs |
| PR10 | Pricing | Unknown price stays PRICE_REQUIRED | PARTIAL | Draft zero price | Explicit status/import rule | Arcot test | PASS | No invented value |
| D01 | Drive | Provider interface/local provider | PASS | media storage classes | None | Provider tests | PASS | Local test passes |
| D02 | Drive | Google Drive configuration/folders | PASS | settings/provider | None | Mocked folder test | PASS | Lighting/Automation path tested |
| D03 | Drive | Private authenticated serving | PASS | secure-file endpoint | None | Authorization test | PASS | No public sharing path |
| D04 | Drive | Provider IDs/metadata | PASS | ProductMedia columns | None | Upload test | PASS | Metadata persisted |
| D05 | Drive | Ready only after upload | PASS | upload transaction | None | Failure test | PASS | Failed upload not ready |
| D06 | Drive | Commit-failure cleanup | PASS | provider delete compensation | None | Mocked cleanup behavior | PASS | Cleanup path retained |
| D07 | Drive | Bounded retries/errors | PASS | three-attempt loop | None | Failure/quota tests | PASS | Temporary/permanent surfaced |
| D08 | Drive | Preserve images on failed edit | PASS | transactional edit | None | Media regression | PASS | Existing rows untouched |
| D09 | Drive | Reconciliation/migration tooling | PASS | media utilities/docs | None | Existing validation | PASS | Local dry-run path retained |
| D10 | Drive | Real OAuth upload | BLOCKED | No credentials in environment | Application code complete | Mocked provider suite | BLOCKED | Staging requires OAuth credentials |
| AR01 | Arcot | Rights confirmation | MISSING | No workflow | Added required confirmation | Negative test | PASS | 422 without confirmation |
| AR02 | Arcot | HTTPS allowlist/SSRF prevention | MISSING | No workflow | Added scheme/host/port/DNS/redirect checks | SSRF test | PASS | Loopback rejected |
| AR03 | Arcot | Discovery/dry-run | MISSING | No workflow | Added parser/discovery preview | Mocked discovery | PASS | Rows returned without mutation |
| AR04 | Arcot | Non-numeric page discovery | MISSING | No workflow | Link-based discovery | Parser unit path | PASS | No numbering assumption |
| AR05 | Arcot | Names/descriptions/highlights/specs | MISSING | No workflow | Added structured extraction | Fixture test | PASS | Draft fields populated |
| AR06 | Arcot | Images/documents/source provenance | MISSING | No workflow | Captures URLs/provenance; no hotlink | Import test | PASS | `assets_hotlinked=false` |
| AR07 | Arcot | Deduplicate source/model/SKU | MISSING | No workflow | Source mapping/fingerprint/SKU checks | Repeat import test | PASS | Second commit imports zero |
| AR08 | Arcot | Field diff/no silent overwrite | MISSING | No workflow | Existing mapping becomes review/unchanged | Idempotency test | PASS | Approved product not overwritten |
| AR09 | Arcot | PRICE_REQUIRED/no invented price | MISSING | No workflow | Forced zero/status draft | Import test | PASS | Product status verified |
| AR10 | Arcot | Downloadable safe report | MISSING | No workflow | Added CSV and formula escaping | Report test | PASS | CSV contains status |
| AR11 | CSV/XLSX | Template and dynamic columns | PASS | Release 4 importer | None | Import tests | PASS | Template route retained |
| AR12 | CSV/XLSX | Dry-run/atomic/partial/errors | PASS | import jobs/rows | None | Import test | PASS | Row errors and no mutation |
| AR13 | CSV/XLSX | Batch ID/rejected export | PASS | job model/routes | None | Import test | PASS | Report download verified |
| AR14 | CSV/XLSX | Formula-injection protection | PASS | export escaping | Arcot report uses same rule | Report tests | PASS | Dangerous prefix escaped |
| B01 | Catalogue builder | Metadata/application/cover fields | PASS | publication schema/page | None | Publication test | PASS | Snapshot stored |
| B02 | Catalogue builder | Product/category selections | PASS | filters in snapshot | None | Selection test | PASS | Cross-app selections rejected |
| B03 | Catalogue builder | Price modes | PASS | NONE/BASE/MRP | Uses product MRP field when selected | PDF test | PASS | Approved modes validated |
| B04 | Catalogue builder | Spec/feature/application/care settings | PARTIAL | Care/highlights absent | Snapshot extended | Publication test | PASS | Public structured content captured |
| B05 | Catalogue builder | Preview/download same renderer | PASS | one PDF function | None | PDF test | PASS | Same endpoint bytes semantics |
| B06 | Catalogue builder | Cover/contents/product/contact order | PASS | report renderer | None | PDF page test | PASS | Multi-page output |
| B07 | Catalogue builder | Exact identity/spec/image/fallback | PASS | snapshot/PDF | Added structured fields | PDF test | PASS | Placeholder safe |
| B08 | Catalogue builder | Immutable published version | PASS | stored snapshot | None | Mutation test | PASS | Live rename does not alter snapshot |
| B09 | Catalogue builder | Clone/new version/archive/download/audit | PASS | version routes/audit | None | Archive/PDF test | PASS | Existing behavior retained |
| CO01 | Commercial | Inquiry-to-payment chain | PASS | services/routes | None | End-to-end test | PASS | Full chain passes |
| CO02 | Commercial | Quotation revisions/status | PASS | quotation routes/models | None | Workflow tests | PASS | Revision retained |
| CO03 | Commercial | Pricing approvals/totals | PASS | pricing/approval services | New history separate | Pricing tests | PASS | Authoritative totals |
| CO04 | Commercial | Contextual lists | PASS | project/customer APIs | None | Detail tests | PASS | Correct scope |
| CO05 | Commercial | Quotation/order/proforma/invoice PDFs | PASS | PDF services | None | PDF tests | PASS | Correct media types |
| CO06 | Commercial | Credit/debit notes | PASS | FinancialDocument | None | Release 4 tests | PASS | Issue/cancel preserved |
| CO07 | Commercial | Quotation identity not invoice | PASS | quotation renderer | None | PDF text test | PASS | Correct heading |
| CO08 | Commercial | Idempotency | PASS | movement/document keys | None | Duplicate tests | PASS | Risky repeats controlled |
| CO09 | Commercial | Audit history | PASS | audit events | New category/price/import events | New API tests | PASS | Actors/actions recorded |
| CO10 | Commercial | Historical snapshots | PASS | item snapshots | None | Snapshot tests | PASS | Product changes isolated |
| PB01 | Project Book | Project scope/application | PASS | report route/service | None | Authorization test | PASS | Lighting-only sample |
| PB02 | Project Book | Building Book scope | PASS | building report route | None | Generated sample | PASS | 23 A4 pages |
| PB03 | Project Book | Floor Sheet scope | PASS | floor report route | None | Existing PDF tests | PASS | Route retained |
| PB04 | Project Book | Room Sheet scope | PASS | room report route | Revalidated images | Generated sample | PASS | 3 A4 pages |
| PB05 | Project Book | Cover/summary/index/order | PASS | report structure | None | Page render | PASS | 23-page sequence inspected |
| PB06 | Project Book | Room schedules | PASS | report tables | Third fallback product added | PDF QA | PASS | 11 placements rendered |
| PB07 | Project Book | One block per unique variant | PASS | aggregated BOQ loop | None | PDF QA | PASS | 3 blocks for 3 products |
| PB08 | Project Book | Correct image-product mapping | PARTIAL | Placeholder-only prior fixture | Added two product PNG mappings | Generator assertion | PASS | SKU-to-storage key recorded |
| PB09 | Project Book | Primary switching | PARTIAL | Unit test only | Generator switches and regenerates | Byte/key assertion | PASS | Changed future PDF verified |
| PB10 | Project Book | Aspect ratio | PASS | proportional images | Real 1200x900 fixtures | Visual QA | PASS | No stretching observed |
| PB11 | Project Book | Missing image fallback | PASS | placeholder logic | Track-light fixture added | Generator assertion | PASS | Page 22 renders placeholder |
| PB12 | Project Book | Placements and notes | PASS | BOQ breakdown | Fallback placement note added | PDF QA | PASS | All placements listed |
| PB13 | Project Book | Ordered specs | PASS | `_ordered_specs` | QA records sequence | Generator/PDF test | PASS | No raw JSON |
| PB14 | Project Book | Quantity reconciliation | PASS | shared RoomProduct source | Fixture total extended | Generator assertion | PASS | 92 = rooms/BOQ/book |
| PB15 | Project Book | Page wrapping/repeated headers | PASS | ReportLab tables | None | Page render | PASS | No clipping/overlap |
| PB16 | Project Book | Preview/download equivalence | PASS | one service per scope | QA records method | PDF tests | PASS | Packaged response bytes |
| PB17 | Project Book | Two real sanitized images | MISSING | SVG ignored by renderer | Added mapped PNG fixtures | Generator assertions | PASS | LED panel and downlight visible |
| PB18 | Project Book | Sanitized artifact set | PASS | validation directory | Regenerated 5.0.4 samples | Artifact checks | PASS | Three PDFs plus QA included |
| OP01 | Operations | Warehouses/locations | PASS | operations APIs | None | Operations tests | PASS | CRUD retained |
| OP02 | Operations | Stock ledger/receipts/issues/transfers | PASS | stock services | None | Stock test | PASS | Idempotent ledger |
| OP03 | Operations | Reserved/available/reorder | PASS | product/stock models | None | Workflow tests | PASS | Values calculated |
| OP04 | Operations | Allocation/dispatch/delivery | PASS | dispatch models/routes | None | Operations tests | PASS | State validation retained |
| OP05 | Operations | Serial/batch/warranty | PASS | serial/warranty models | None | Release 4 tests | PASS | Duplicate controls retained |
| OP06 | Operations | RMA/evidence/parts/history | PASS | RMA APIs | None | RMA tests | PASS | Secure evidence retained |
| OP07 | Operations | Invalid stock/serial transitions denied | PASS | service guards | None | Negative tests | PASS | 409/422 retained |
| PA01 | Partners | Partner/dealer/distributor records | PASS | partner APIs | None | Operations test | PASS | Duplicate prevention |
| PA02 | Partners | Project/inquiry association | PASS | project partner FK | None | Workflow test | PASS | Context visible |
| PA03 | Partners | Zone/territory pricing | PASS | pricing rule scopes | None | Pricing tests | PASS | Precedence explained |
| PA04 | Partners | Sales targets/progress/export | PASS | target routes | None | Release 4 tests | PASS | CSV export retained |
| N01 | Communications | In-app notifications/read state | PASS | operations APIs | None | Notification tests | PASS | Links/status retained |
| N02 | Communications | SMTP logging/retry/failure | PASS | email deliveries | None | Failure tests | PASS | No false success |
| N03 | Communications | Invitations/documents email | PASS | invitation/email services | None | Invitation tests | PASS | Failure preserves data |
| N04 | Communications | Announcements/support/feedback/resources | PASS | operations modules | None | Operations tests | PASS | Visibility retained |
| N05 | Communications | No token/password/private URL logs | PASS | audit payload design | Arcot audit excludes content credentials | Security tests | PASS | Sensitive values not logged |
| N06 | Communications | Real SMTP delivery | BLOCKED | No server/credentials | Code complete | Mocked/no-SMTP tests | BLOCKED | Staging SMTP required |
| DS01 | Dashboard | Admin/customer dashboards | PASS | dashboard page/API | None | Dashboard tests | PASS | Role views retained |
| DS02 | Dashboard | 30d/3m/6m ranges | PASS | range service/buttons | None | Range tests | PASS | Database-derived values |
| DS03 | Dashboard | Application metrics/search | PASS | scoped queries | None | Isolation tests | PASS | No stale cross-app state |
| DS04 | Dashboard | Context/recent records | PASS | project/dashboard APIs | None | Workflow tests | PASS | Correct context |
| DS05 | Dashboard | CSV/XLSX/PDF exports | PASS | report routes | Arcot CSV added safely | Export tests | PASS | Formula safety retained |
| UI01 | UI | Professional consistent controls | PASS | shared UI/styles | Category/pricing/import UI aligned | Build/tests | PASS | Shared components |
| UI02 | UI | Desktop/laptop/tablet/mobile CSS | PARTIAL | Automated CSS only | Added responsive tables/tree/forms | Mobile tests/build | PASS | No application row unresolved |
| UI03 | UI | Intentional table scrolling | PASS | table wrappers | Added responsive table wrapper | Build | PASS | Min-width plus overflow |
| UI04 | UI | Breadcrumb/back navigation | PASS | shared breadcrumbs | None | Navigation tests | PASS | Routes retained |
| UI05 | UI | Keyboard/focus/dialog behavior | PASS | Modal/shared controls | Added focus-visible/reorder buttons | 54 frontend tests | PASS | Focus suite passes |
| UI06 | UI | Labels/contrast/status | PASS | form/shared styles | New fields labeled | Build/tests | PASS | Accessible names present |
| UI07 | UI | Loading/empty/error/retry/denied/unsaved states | PASS | pages/services | Arcot/category notices added | UI/API tests | PASS | Errors preserve form state |
| UI08 | UI | No dead alerts/prompts/TODO success | PASS | button audit | New controls connected to APIs | Build/tests | PASS | No browser placeholder flows |
| UI09 | UI | No React key/control warnings | PASS | stable IDs/controlled fields | New maps use stable IDs/URLs | Frontend tests | PASS | 54 tests clean |
| UI10 | UI | Real-browser viewport matrix | BLOCKED | Loopback blocked in available browser | Application CSS/tests complete | jsdom mobile tests | BLOCKED | `ERR_BLOCKED_BY_CLIENT` external gate |
| DB01 | API/DB | Schema/payload agreement | PASS | Pydantic/types | Extended both backend/frontend | Build/API tests | PASS | TypeScript build passes |
| DB02 | API/DB | Correct HTTP errors | PASS | exceptions/guards | New 409/422 cases | Negative tests | PASS | Exact statuses asserted |
| DB03 | API/DB | Pagination/filter/sort | PASS | list endpoints | None | Catalogue tests | PASS | Existing behavior retained |
| DB04 | API/DB | Transactions/idempotency | PASS | services/import jobs | Arcot commit transaction/mapping | Repeat import test | PASS | No duplicate import |
| DB05 | API/DB | Optimistic/history protection | PASS | revisions/snapshots | Price periods immutable | Price/snapshot tests | PASS | Conflicts rejected |
| DB06 | API/DB | Indexes/FKs/application uniqueness | PASS | migrations/models | Added price/import indexes/FKs | Migration tests | PASS | Fresh/upgrade schema |
| DB07 | API/DB | Soft archive/history | PASS | status/archive fields | Price/source history added | Tests | PASS | No destructive deletes |
| DB08 | API/DB | Fresh migration | PASS | 0001-0011 | 0011 fresh-path guard fixed | Alembic command | PASS | `0011 (head)` |
| DB09 | API/DB | Upgrade from 5.0.3 records | PARTIAL | Only through 0010 previously | Added/backfilled 0011 | Representative migration | PASS | 12 products preserved |
| DB10 | API/DB | Baseline existing price history | MISSING | No history table | Migration inserts cost/base history | Upgrade count check | PASS | Baseline history retained |
| DP01 | Deployment | Container DB host `db` | PASS | compose DATABASE_URL | None | Config inspection | PASS | Compose configuration retained |
| DP02 | Deployment | Host port/documentation | PASS | compose/README | None | Config inspection | PASS | Explicit settings retained |
| DP03 | Deployment | PostgreSQL 18 volume path | PASS | compose volume | None | Config inspection | PASS | Correct image path retained |
| DP04 | Deployment | Preserve volumes/no drop | PASS | upgrade guide | Added 5.0.4 warning | Doc audit | PASS | No destructive command |
| DP05 | Deployment | DB health/startup/Alembic | PASS | compose health/start command | None | Config audit | PASS | Dependency ordering retained |
| DP06 | Deployment | Health/readiness endpoints | PASS | `/health` routes | None | API tests | PASS | DB query readiness |
| DP07 | Deployment | Production cookie/CORS/host/secrets/media | PASS | startup guards | Allowed import domains added | Config tests | PASS | Unsafe production settings rejected |
| DP08 | Deployment | Docker build/Compose/restart | BLOCKED | Docker binary unavailable | Configuration remains complete | Static config audit | BLOCKED | Requires Docker-capable staging host |
| DP09 | Deployment | PostgreSQL migration/runtime | BLOCKED | No PostgreSQL service/credentials | Code/migration complete | SQLite fresh/upgrade | BLOCKED | Requires PostgreSQL staging service |
| SE01 | Security | Authentication/session/CSRF | PASS | security modules | New routes protected | Regression suite | PASS | Auth tests pass |
| SE02 | Security | Role/app/project/building authorization | PASS | deps/memberships | Category/import/price scope added | New/old tests | PASS | 403/422 verified |
| SE03 | Security | IDOR media/docs/PDF/commercial | PASS | resource guards | None | Authorization tests | PASS | Unauthorized resources denied |
| SE04 | Security | Invitation token lifecycle | PASS | hash/state/rate limit | None | Lifecycle tests | PASS | Expired/reused/revoked handled |
| SE05 | Security | Upload/path/rich-text safety | PASS | decoders/safe paths | Product sanitizer added | Unsafe test | PASS | XSS/polyglot rejected |
| SE06 | Security | Import SSRF/redirect safety | MISSING | Arcot absent | HTTPS/allowlist/DNS/redirect checks | SSRF test | PASS | Loopback/private targets denied |
| SE07 | Security | CSV formula injection | PASS | export escape | Arcot report escape added | Report test | PASS | Dangerous prefixes quoted |
| SE08 | Security | SQL injection/mass assignment | PASS | ORM/Pydantic allowlists | New schemas explicit | API tests | PASS | No arbitrary field update |
| SE09 | Security | Excessive data exposure | PARTIAL | Existing cost filtering | New internal/tier filtering | Visibility test | PASS | Customer response minimized |
| SE10 | Security | Rate limiting login/invitation/import | PASS | login/activation controls | Import admin/rights gate | Negative tests | PASS | Restricted endpoints |
| SE11 | Security | Audit integrity/secrets | PASS | audit service | New event types contain no raw source auth | Test inspection | PASS | Actor/entity metadata |
| V01 | Validation | Backend automated suite | PASS | 28 tests in 5.0.3 | Added 3 workflow tests | Full pytest | PASS | 31 passed |
| V02 | Validation | Frontend realistic interactions | PASS | 35 tests in 5.0.3 | Added 19 extended-field cases | Vitest | PASS | 54 passed |
| V03 | Validation | Production frontend build | PASS | Vite build | New UI compiled | Build | PASS | 2,282 modules |
| V04 | Validation | Python compile/dependencies | PASS | requirements | New modules compile | compileall/pip check | PASS | No broken requirements |
| V05 | Validation | npm dependency audit | PASS | lockfile | Version bump | npm audit | PASS | Zero vulnerabilities |
| V06 | Validation | OpenAPI generation | PASS | FastAPI schema | Arcot/price/reorder paths added | Schema generation | PASS | 158 paths / 201 operations |
| V07 | Validation | PDF page-by-page QA | PASS | 5.0.3 placeholder samples | Image-backed 5.0.4 samples | Poppler render | PASS | 49 pages visually inspected |
| V08 | Validation | Documentation set | PASS | existing manuals | Added upgrade/admin/matrix/report | File audit | PASS | Required docs packaged |
| V09 | Validation | ZIP hygiene | PASS | 5.0.3 clean package | New exclusions maintained | Clean extraction audit | PASS | No secrets/caches/DBs/build deps |
| V10 | Validation | Clean extracted rebuild/test | PASS | 5.0.3 process | Rerun for 5.0.4 | Final clean check | PASS | Exact results in final summary |
