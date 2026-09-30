-- AlphaNumeric B2B: Arcot COB CA1-CA10 seed/import
-- Target: PostgreSQL, AlphaNumeric schema at Alembic revision 0011
-- Source facts reviewed from https://arcotindia.com/cobs-1 through /cobs-10
-- Marketing descriptions below are original paraphrases; prices, tax, stock,
-- HSN/SAC and lead time are intentionally not invented.
--
-- Safety properties:
--   * one transaction
--   * no DELETE/TRUNCATE/DROP of persistent objects
--   * reuses an existing Lighting > Lights > COB hierarchy where present
--   * idempotent by SKU (ARCOT-COB-CA1 through ARCOT-COB-CA10)
--   * refuses to overwrite a colliding SKU owned by another manufacturer/app
--   * rolls back automatically if all ten records are not present at the end

BEGIN;

CREATE TEMP TABLE arcot_cob_seed (
    model_number text PRIMARY KEY,
    wattage text NOT NULL,
    size_value text NOT NULL,
    cutout text NOT NULL,
    source_url text NOT NULL
) ON COMMIT DROP;

INSERT INTO arcot_cob_seed (model_number, wattage, size_value, cutout, source_url)
VALUES
    ('CA1',  '20W / 30W-35W / 40W-45W (customizable)',
             '90x109 / 115x125 / 130x140 mm (customizable)',
             '75 / 95 / 95 / 115 mm',
             'https://arcotindia.com/cobs-1'),
    ('CA2',  '20W / 30W-35W / 40W-45W (customizable)',
             '90x90x109 / 115x115x125 / 130x130x140 mm (customizable)',
             '75x75 / 95x95 / 115x115 mm',
             'https://arcotindia.com/cobs-2'),
    ('CA3',  '2x20W / 2x(30W-35W) / 2x(40W-45W) (customizable)',
             '90x169x109 / 115x216x125 / 130x245x140 mm (customizable)',
             '150x75 / 193x95 / 220x115 mm',
             'https://arcotindia.com/cobs-3'),
    ('CA4',  '7W (customizable)',
             '40x76.5 mm (customizable)',
             '35 mm',
             'https://arcotindia.com/cobs-4'),
    ('CA5',  '10W (customizable)',
             '50x88.5 mm (customizable)',
             '45 mm',
             'https://arcotindia.com/cobs-5'),
    ('CA6',  '10W-12W (customizable)',
             '62x106.5 mm (customizable)',
             '45 mm',
             'https://arcotindia.com/cobs-6'),
    ('CA7',  '10W-12W (customizable)',
             '70x106.5 mm (customizable)',
             '45 mm',
             'https://arcotindia.com/cobs-7'),
    ('CA8',  '10W-12W (customizable)',
             '62x62x106.5 mm (customizable)',
             '45 mm',
             'https://arcotindia.com/cobs-8'),
    ('CA9',  '10W-12W (customizable)',
             '70x70x106.5 mm (customizable)',
             '45 mm',
             'https://arcotindia.com/cobs-9'),
    ('CA10', '2x(10W-12W) (customizable)',
             '115.5x62x106.5 mm (customizable)',
             '45 mm',
             'https://arcotindia.com/cobs-10');

DO $seed$
DECLARE
    v_lights_category_id text;
    v_cob_category_id text;
    v_family_id text;
    v_conflicting_skus text;
    v_final_count integer;
BEGIN
    -- Refuse to repurpose an existing SKU belonging to another record scope.
    SELECT string_agg(p.sku, ', ' ORDER BY p.sku)
      INTO v_conflicting_skus
      FROM products p
     WHERE p.sku IN (
               SELECT 'ARCOT-COB-' || s.model_number
                 FROM arcot_cob_seed s
           )
       AND (
               p.workspace <> 'LIGHTING'
            OR COALESCE(p.manufacturer, '') <> 'Arcot India Private Limited'
           );

    IF v_conflicting_skus IS NOT NULL THEN
        RAISE EXCEPTION
            'Import stopped: these SKUs already belong to unrelated records: %',
            v_conflicting_skus;
    END IF;

    -- Reuse or create the root Lighting category named Lights.
    SELECT c.id
      INTO v_lights_category_id
      FROM categories c
     WHERE c.workspace = 'LIGHTING'
       AND c.parent_id IS NULL
       AND lower(c.name) = 'lights'
     ORDER BY c.created_at, c.id
     LIMIT 1;

    IF v_lights_category_id IS NULL THEN
        v_lights_category_id := gen_random_uuid()::text;

        INSERT INTO categories (
            id, workspace, name, slug, parent_id,
            short_description, full_description,
            catalogue_visible, customer_visible, search_visible,
            page_title, meta_description, status, sort_order,
            created_at, updated_at
        )
        VALUES (
            v_lights_category_id, 'LIGHTING', 'Lights', 'lights', NULL,
            'Indoor and architectural lighting products.',
            'Lighting products organized by technology and installation type.',
            true, true, true,
            'Lights', 'Lighting products and configurable luminaires.',
            'ACTIVE', 10, now(), now()
        );
    END IF;

    -- Reuse or create COB beneath Lights.
    SELECT c.id
      INTO v_cob_category_id
      FROM categories c
     WHERE c.workspace = 'LIGHTING'
       AND c.parent_id = v_lights_category_id
       AND lower(c.name) = 'cob'
     ORDER BY c.created_at, c.id
     LIMIT 1;

    IF v_cob_category_id IS NULL THEN
        v_cob_category_id := gen_random_uuid()::text;

        INSERT INTO categories (
            id, workspace, name, slug, parent_id,
            short_description, full_description,
            catalogue_visible, customer_visible, search_visible,
            page_title, meta_description, status, sort_order,
            created_at, updated_at
        )
        VALUES (
            v_cob_category_id, 'LIGHTING', 'COB', 'cob',
            v_lights_category_id,
            'Chip-on-board luminaires for focused architectural lighting.',
            'Configurable COB luminaires for residential, retail, hospitality and commercial applications.',
            true, true, true,
            'COB Luminaires',
            'High-CRI COB luminaires with configurable wattage, optics, CCT and controls.',
            'ACTIVE', 10, now(), now()
        );
    END IF;

    -- One family with ten exact sellable variants/models.
    INSERT INTO product_families (
        id, workspace, category_id, name, slug, brand,
        short_description, full_description,
        features, applications, suitability_guidance,
        status, created_at, updated_at
    )
    VALUES (
        gen_random_uuid()::text,
        'LIGHTING',
        v_cob_category_id,
        'Arcot COB Series',
        'arcot-cob-series',
        'Arcot',
        'Configurable high-CRI COB luminaires in black or white aluminium bodies.',
        'A family of compact and multi-head COB luminaires with selectable wattage, CCT, beam optics, ingress-protection options and wired or smart-control protocols.',
        '["High CRI above 90", "Multiple beam-angle choices", "Selectable CCT", "Black or white aluminium body", "Multiple driver and control options", "Rated life above 40,000 hours"]'::json,
        '["Residential lighting", "Retail and showroom lighting", "Hospitality lighting", "Office lighting", "Architectural accent lighting"]'::json,
        'Confirm the final wattage, dimensions, cutout, IP rating, driver and control protocol before quotation or installation.',
        'ACTIVE', now(), now()
    )
    ON CONFLICT (workspace, slug)
    DO UPDATE SET
        category_id = EXCLUDED.category_id,
        name = EXCLUDED.name,
        brand = EXCLUDED.brand,
        short_description = EXCLUDED.short_description,
        full_description = EXCLUDED.full_description,
        features = EXCLUDED.features,
        applications = EXCLUDED.applications,
        suitability_guidance = EXCLUDED.suitability_guidance,
        status = 'ACTIVE',
        updated_at = now()
    RETURNING id INTO v_family_id;

    -- Definitions make the imported specifications editable, searchable and
    -- consistently ordered in the catalogue, room picker and generated PDFs.
    WITH definitions (
        spec_key, label, help_text, sort_order,
        show_in_quotation_pdf, searchable
    ) AS (
        VALUES
            ('wattage',              'Wattage',               'Select the final project wattage before quotation.',  10, true,  true),
            ('input_voltage',         'Input Voltage',          NULL,                                                20, true,  true),
            ('cct',                   'CCT',                    'Correlated colour-temperature choices.',             30, true,  true),
            ('cri',                   'CRI',                    'Colour rendering index.',                             40, true,  true),
            ('beam_angle',            'Beam Angle',             'Available optical beam choices.',                     50, true,  true),
            ('reflector_color',       'Reflector Color',        NULL,                                                60, false, true),
            ('body_color',            'Body Color',             NULL,                                                70, false, true),
            ('size',                  'Size',                   'Published body dimensions; confirm final selection.', 80, false, false),
            ('cutout',                'Cutout',                 'Published cutout; confirm against selected variant.', 90, true,  false),
            ('led_make',              'LED Make',               NULL,                                               100, false, true),
            ('led_source',            'LED Source',             NULL,                                               110, false, false),
            ('operating_temperature', 'Operating Temperature',  NULL,                                               120, false, false),
            ('rated_life',            'Rated Life',             NULL,                                               130, false, false),
            ('ip_rating',             'IP Rating',              'Confirm the required ingress-protection option.',    140, true,  true),
            ('driver',                'Driver',                 'Available driver makes.',                            150, false, true),
            ('protocols',             'Control Protocols',      'Available wired and wireless control options.',      160, true,  true),
            ('warranty',              'Warranty',               'Subject to confirmed commercial warranty terms.',   170, false, false),
            ('body_material',         'Body Material',          NULL,                                               180, false, false)
    )
    INSERT INTO product_spec_definitions (
        id, category_id, workspace, product_family_id,
        spec_key, label, help_text, data_type, unit,
        allowed_units, default_value, min_value, max_value, precision,
        required, allowed_values, sort_order,
        show_in_catalogue, show_in_project_book, show_in_quotation_pdf,
        show_in_customer_portal, show_in_room_picker, show_in_exports,
        searchable, status
    )
    SELECT
        gen_random_uuid()::text,
        v_cob_category_id,
        'LIGHTING',
        v_family_id,
        d.spec_key,
        d.label,
        d.help_text,
        'text',
        NULL,
        '[]'::json,
        NULL,
        NULL,
        NULL,
        NULL,
        false,
        '[]'::json,
        d.sort_order,
        true,
        true,
        d.show_in_quotation_pdf,
        true,
        true,
        true,
        d.searchable,
        'ACTIVE'
    FROM definitions d
    ON CONFLICT (workspace, category_id, product_family_id, spec_key)
    DO UPDATE SET
        label = EXCLUDED.label,
        help_text = EXCLUDED.help_text,
        data_type = EXCLUDED.data_type,
        sort_order = EXCLUDED.sort_order,
        show_in_catalogue = EXCLUDED.show_in_catalogue,
        show_in_project_book = EXCLUDED.show_in_project_book,
        show_in_quotation_pdf = EXCLUDED.show_in_quotation_pdf,
        show_in_customer_portal = EXCLUDED.show_in_customer_portal,
        show_in_room_picker = EXCLUDED.show_in_room_picker,
        show_in_exports = EXCLUDED.show_in_exports,
        searchable = EXCLUDED.searchable,
        status = 'ACTIVE';

    INSERT INTO products (
        id, workspace, category_id, family_id,
        sku, name, internal_name, description, full_description,
        brand, manufacturer, variant_name, model_number,
        search_tags, highlights, features, applications,
        installation_summary, care_guide, warranty_summary, internal_notes,
        status, on_hand, reserved, reorder_level, unit,
        price, cost, mrp_price, project_price, dealer_price, reseller_price,
        currency, minimum_order_quantity, pricing_status,
        tax_rate, hsn_sac, specs, images,
        lead_time_days, warranty, created_at, updated_at
    )
    SELECT
        gen_random_uuid()::text,
        'LIGHTING',
        v_cob_category_id,
        v_family_id,
        'ARCOT-COB-' || s.model_number,
        'Arcot COB ' || s.model_number,
        'Arcot COB ' || s.model_number,
        format(
            'Configurable %s COB luminaire with high-CRI optics, selectable CCT, multiple beam angles and black or white aluminium construction.',
            s.model_number
        ),
        format(
            'Arcot %s is a configurable COB luminaire intended for focused residential and commercial illumination. The published configuration includes %s output options, a %s body envelope and a %s cutout. Final wattage, IP rating, driver and control protocol must be selected for the project.',
            s.model_number, s.wattage, s.size_value, s.cutout
        ),
        'Arcot',
        'Arcot India Private Limited',
        s.model_number,
        s.model_number,
        json_build_array(
            'Arcot', 'COB', lower(s.model_number), 'downlight',
            'high CRI', 'configurable', 'lighting'
        ),
        json_build_array(
            s.wattage,
            'CRI > 90',
            '3000K / 4000K / 6500K',
            'IP20 / IP54 option',
            '5-year listed warranty'
        ),
        '["Selectable beam angles: 15°, 24°, 36° or 50°", "Black or white reflector and body", "BLX, CREE, OSRAM or LUMI LED option", "FULLHAM, PHILIPS or BAG driver option", "Multiple wired and wireless control protocols", "Aluminium body"]'::json,
        '["Homes", "Offices", "Retail and showrooms", "Hotels and hospitality", "Architectural accent lighting"]'::json,
        format(
            'Installation must be completed by a qualified electrician. Confirm the selected %s configuration and prepare the listed %s cutout before fitting. Maintain airflow around the luminaire and driver.',
            s.model_number, s.cutout
        ),
        'Disconnect power before cleaning or inspection. Use a soft dry or lightly damp cloth, avoid abrasive chemicals and excess moisture, periodically inspect connections and ventilation, and handle the fitting carefully during installation or relocation.',
        'The source catalogue lists a five-year warranty. Confirm the final warranty terms, driver coverage and project-specific exclusions before sale.',
        format(
            'Imported from %s on 2026-09-24. Commercial prices, GST/tax rate, HSN/SAC, lead time and stock were not published and remain unapproved.',
            s.source_url
        ),
        'ACTIVE',
        0.00,
        0.00,
        0.00,
        'Nos',
        0.00,
        NULL,
        NULL,
        NULL,
        NULL,
        NULL,
        'INR',
        1.00,
        'DRAFT',
        0.00,
        NULL,
        json_build_object(
            'wattage', s.wattage,
            'input_voltage', '220-240V AC',
            'cct', '3000K / 4000K / 6500K',
            'cri', '>90',
            'beam_angle', '15° / 24° / 36° / 50°',
            'reflector_color', 'Black / White',
            'body_color', 'Black / White',
            'size', s.size_value,
            'cutout', s.cutout,
            'led_make', 'BLX / CREE / OSRAM / LUMI',
            'led_source', '5050',
            'operating_temperature', '45-50°C',
            'rated_life', '40,000+ hours',
            'ip_rating', 'IP20 / IP54',
            'driver', 'FULLHAM / PHILIPS / BAG',
            'protocols', 'ON/OFF / Triac / Phase Cut / RF / Wi-Fi / TUYA / Zigbee / DT6 / DT8 / CASAMBI',
            'warranty', '5 years',
            'body_material', 'Aluminium',
            'source_url', s.source_url
        ),
        '[]'::json,
        NULL,
        '5 Years',
        now(),
        now()
    FROM arcot_cob_seed s
    ON CONFLICT (sku)
    DO UPDATE SET
        workspace = EXCLUDED.workspace,
        category_id = EXCLUDED.category_id,
        family_id = EXCLUDED.family_id,
        name = EXCLUDED.name,
        internal_name = EXCLUDED.internal_name,
        description = EXCLUDED.description,
        full_description = EXCLUDED.full_description,
        brand = EXCLUDED.brand,
        manufacturer = EXCLUDED.manufacturer,
        variant_name = EXCLUDED.variant_name,
        model_number = EXCLUDED.model_number,
        search_tags = EXCLUDED.search_tags,
        highlights = EXCLUDED.highlights,
        features = EXCLUDED.features,
        applications = EXCLUDED.applications,
        installation_summary = EXCLUDED.installation_summary,
        care_guide = EXCLUDED.care_guide,
        warranty_summary = EXCLUDED.warranty_summary,
        internal_notes = EXCLUDED.internal_notes,
        status = 'ACTIVE',
        unit = EXCLUDED.unit,
        pricing_status = 'DRAFT',
        specs = EXCLUDED.specs,
        warranty = EXCLUDED.warranty,
        updated_at = now()
    WHERE products.workspace = 'LIGHTING'
      AND products.manufacturer = 'Arcot India Private Limited';

    -- Mirror the JSON specifications into normalized values used by ordered
    -- Project Book/quotation rendering and the dynamic specification editor.
    INSERT INTO product_spec_values (
        id, product_id, definition_id, value, created_at, updated_at
    )
    SELECT
        gen_random_uuid()::text,
        p.id,
        d.id,
        json_build_object(
            'value', p.specs ->> d.spec_key,
            'unit', d.unit,
            'type', d.data_type
        ),
        now(),
        now()
    FROM products p
    JOIN product_spec_definitions d
      ON d.workspace = p.workspace
     AND d.category_id = p.category_id
     AND d.product_family_id = p.family_id
     AND d.status = 'ACTIVE'
    WHERE p.workspace = 'LIGHTING'
      AND p.manufacturer = 'Arcot India Private Limited'
      AND p.sku IN (
          SELECT 'ARCOT-COB-' || s.model_number
          FROM arcot_cob_seed s
      )
      AND p.specs ->> d.spec_key IS NOT NULL
    ON CONFLICT (product_id, definition_id)
    DO UPDATE SET
        value = EXCLUDED.value,
        updated_at = now();

    SELECT count(*)
      INTO v_final_count
      FROM products p
     WHERE p.workspace = 'LIGHTING'
       AND p.manufacturer = 'Arcot India Private Limited'
       AND p.sku IN (
               SELECT 'ARCOT-COB-' || s.model_number
                 FROM arcot_cob_seed s
           );

    IF v_final_count <> 10 THEN
        RAISE EXCEPTION
            'Import validation failed: expected 10 Arcot COB products, found %',
            v_final_count;
    END IF;
END
$seed$;

COMMIT;

-- Verification output: this should return exactly ten rows.
SELECT
    p.sku,
    p.name,
    p.model_number,
    p.pricing_status,
    p.price,
    p.tax_rate,
    p.specs ->> 'wattage' AS wattage,
    p.specs ->> 'size' AS size,
    p.specs ->> 'cutout' AS cutout
FROM products p
WHERE p.workspace = 'LIGHTING'
  AND p.manufacturer = 'Arcot India Private Limited'
  AND p.sku IN (
      'ARCOT-COB-CA1', 'ARCOT-COB-CA2', 'ARCOT-COB-CA3',
      'ARCOT-COB-CA4', 'ARCOT-COB-CA5', 'ARCOT-COB-CA6',
      'ARCOT-COB-CA7', 'ARCOT-COB-CA8', 'ARCOT-COB-CA9',
      'ARCOT-COB-CA10'
  )
ORDER BY
    substring(p.model_number FROM '[0-9]+')::integer;
