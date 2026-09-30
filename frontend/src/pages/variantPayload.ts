export type VariantSpecDefinition = {
  spec_key: string;
  data_type: string;
};

type VariantForm = {
  [key: string]: unknown;
  specs: Record<string, unknown>;
};

const decimal = (value: unknown, label: string, optional = false, strictlyPositive = false) => {
  const raw = String(value ?? "").trim();
  if (!raw && optional) return null;
  if (!/^(?:\d+)(?:\.\d+)?$/.test(raw) || (strictlyPositive && !/[1-9]/.test(raw))) {
    throw new Error(`${label} must be ${strictlyPositive ? "greater than zero" : "a non-negative number"}.`);
  }
  // A decimal string reaches Pydantic's Decimal unchanged, without binary float rounding.
  return raw;
};

export function buildVariantPayload(form: VariantForm, definitions: VariantSpecDefinition[], editing: boolean) {
  const text = (key: string) => String(form[key] ?? "").trim();
  const optional = (key: string) => text(key) || null;
  const lines = (key: string, separator: RegExp) => text(key).split(separator).map(x => x.trim()).filter(Boolean);
  if (!text("name")) throw new Error("Display name is required.");
  if (!text("unit")) throw new Error("Unit is required.");
  const lead = text("lead_time_days");
  if (lead && (!/^\d+$/.test(lead))) throw new Error("Lead time must be a non-negative whole number.");
  const specs: Record<string, unknown> = {};
  // Catalogue provenance is stored with imported products, but is not an
  // editable technical specification. Never send it through the PATCH form.
  if (!definitions.length) Object.assign(specs, Object.fromEntries(
    Object.entries(form.specs).filter(([key]) => key !== "source_url"),
  ));
  for (const definition of definitions) {
    const raw = form.specs[definition.spec_key];
    if (raw === undefined || raw === null || raw === "" || (Array.isArray(raw) && !raw.length)) continue;
    if (definition.data_type === "measurement") {
      const value = raw as {amount?: unknown; unit?: string};
      if (String(value.amount ?? "").trim())
        specs[definition.spec_key] = {amount: decimal(value.amount, definition.spec_key), unit: value.unit};
    } else if (definition.data_type === "decimal") specs[definition.spec_key] = decimal(raw, definition.spec_key);
    else if (definition.data_type === "number") {
      if (!/^-?\d+$/.test(String(raw).trim())) throw new Error(`${definition.spec_key} must be a whole number.`);
      specs[definition.spec_key] = Number(raw);
    } else specs[definition.spec_key] = raw;
  }
  return {
    ...(!editing ? {sku: text("sku"), on_hand: decimal(form.on_hand, "Opening stock")} : {}),
    name: text("name"), internal_name: optional("internal_name"), variant_name: optional("variant_name"),
    model_number: optional("model_number"), barcode: optional("barcode"), manufacturer: optional("manufacturer"),
    search_tags: lines("search_tags", /,/), description: optional("description"),
    full_description: optional("full_description"), highlights: lines("highlights", /\n/),
    features: lines("features", /\n/), applications: lines("applications", /\n/),
    installation_summary: optional("installation_summary"), care_guide: optional("care_guide"),
    warranty_summary: optional("warranty_summary"), internal_notes: optional("internal_notes"),
    unit: text("unit"), price: decimal(form.price, "Price"), cost: decimal(form.cost, "Cost", true),
    mrp_price: decimal(form.mrp_price, "MRP", true), project_price: decimal(form.project_price, "Project price", true),
    dealer_price: decimal(form.dealer_price, "Dealer price", true),
    reseller_price: decimal(form.reseller_price, "Reseller price", true),
    currency: text("currency"), minimum_order_quantity: decimal(form.minimum_order_quantity, "Minimum order quantity", false, true),
    pricing_status: text("pricing_status"), tax_rate: decimal(form.tax_rate, "Tax rate"),
    hsn_sac: optional("hsn_sac"), reorder_level: decimal(form.reorder_level, "Reorder level"),
    lead_time_days: lead ? Number(lead) : null, warranty: optional("warranty"), specs,
  };
}
