import { useEffect, useMemo, useRef, useState } from "react";

import {

   ArrowLeft,

   CheckCircle2,

   FileImage,

   ImagePlus,

   Images,

   Maximize2,

   PackagePlus,

   Pencil,

   Star,

   Trash2,

   Upload,

} from "lucide-react";

import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { api, del, patch, post } from "../api/client";

import { useAuth } from "../app/AuthContext";

import {

   Breadcrumbs,

   Button,

   Card,

   Empty,

   Modal,

   Notice,

   PageTitle,

   ProductImage,

   Status,

   money,

} from "../components/UI";

import type { Product, ProductFamily, ProductMedia } from "../types";

import "../product-media-upload.css";
import "../product-detail-premium.css";

import { buildVariantPayload } from "./variantPayload";




type SpecDefinition = {

   spec_key: string;

   label: string;

   help_text?: string | null;

   data_type: string;

   unit?: string | null;

   allowed_units: string[];

   required: boolean;

   allowed_values: string[];

   min_value?: number | null;

   max_value?: number | null;

   precision?: number | null;

};

type PriceHistory = {id:string;price_type:string;amount:number;currency:string;effective_from:string;effective_until?:string|null;status:string;approval_note?:string|null};

const variantInitial = {

   sku: "",

   name: "",

   internal_name: "",

   variant_name: "",

   model_number: "",

   barcode: "",

   manufacturer: "",

   search_tags: "",

   description: "",

   full_description: "",

   highlights: "",

   features: "",

   applications: "",

   installation_summary: "",

   care_guide: "",

   warranty_summary: "",

   internal_notes: "",

   unit: "Nos",

   price: "0",

   cost: "",

   mrp_price: "",

   project_price: "",

   dealer_price: "",

   reseller_price: "",

   currency: "INR",

   minimum_order_quantity: "1",

   pricing_status: "DRAFT",

   tax_rate: "18",

   hsn_sac: "",

   on_hand: "0",

   reorder_level: "10",

   lead_time_days: "",

   warranty: "",

   specs: {} as Record<string, unknown>,

};



function SpecificationField({

   definition,

   value,

   onChange,

}: {

   definition: SpecDefinition;

   value: unknown;

   onChange: (value: unknown) => void;

}) {

   const hint = (

      <small>

         {[definition.help_text, definition.unit].filter(Boolean).join(" · ")}

      </small>

   );

   if (definition.data_type === "boolean")

      return (

         <label>

            {definition.label}

            {definition.required ? " *" : ""}

            <select

               value={value === undefined ? "" : String(value)}

               onChange={(e) =>

                  onChange(e.target.value === "" ? "" : e.target.value === "true")

               }

            >

               <option value="">Select</option>

               <option value="true">Yes</option>

               <option value="false">No</option>

            </select>

            {hint}

         </label>

      );

   if (definition.data_type === "single_select")

      return (

         <label>

            {definition.label}

            {definition.required ? " *" : ""}

            <select

               value={String(value ?? "")}

               onChange={(e) => onChange(e.target.value)}

            >

               <option value="">Select</option>

               {definition.allowed_values.map((item) => (

                  <option key={item}>{item}</option>

               ))}

            </select>

            {hint}

         </label>

      );

   if (definition.data_type === "multi_select")

      return (

         <label>

            {definition.label}

            {definition.required ? " *" : ""}

            <select

               multiple

               value={Array.isArray(value) ? value.map(String) : []}

               onChange={(e) =>

                  onChange(

                     Array.from(e.target.selectedOptions, (option) => option.value),

                  )

               }

            >

               {definition.allowed_values.map((item) => (

                  <option key={item}>{item}</option>

               ))}

            </select>

            {hint}

         </label>

      );

   if (definition.data_type === "long_text")

      return (

         <label>

            {definition.label}

            {definition.required ? " *" : ""}

            <textarea

               value={String(value ?? "")}

               onChange={(e) => onChange(e.target.value)}

            />

            {hint}

         </label>

      );

   if (definition.data_type === "measurement") {

      const measurement = (value && typeof value === "object" ? value : {}) as {

         amount?: string | number;

         unit?: string;

      };

      return (

         <label>

            {definition.label}

            {definition.required ? " *" : ""}

            <span className="measurement-input">

               <input

                  type="number"

                  step={

                     definition.precision == null ? "any" : 10 ** -definition.precision

                  }

                  min={definition.min_value ?? undefined}

                  max={definition.max_value ?? undefined}

                  value={measurement.amount ?? ""}

                  onChange={(e) =>

                     onChange({ ...measurement, amount: e.target.value })

                  }

               />

               {definition.allowed_units.length ? (

                  <select

                     value={measurement.unit || definition.unit || ""}

                     onChange={(e) =>

                        onChange({ ...measurement, unit: e.target.value })

                     }

                  >

                     {definition.allowed_units.map((item) => (

                        <option key={item}>{item}</option>

                     ))}

                  </select>

               ) : (

                  <input

                     value={measurement.unit || definition.unit || ""}

                     onChange={(e) =>

                        onChange({ ...measurement, unit: e.target.value })

                     }

                  />

               )}

            </span>

            {hint}

         </label>

      );

   }

   const numeric =

      definition.data_type === "number" || definition.data_type === "decimal";

   return (

      <label>

         {definition.label}

         {definition.required ? " *" : ""}

         <input

            type={

               definition.data_type === "date" ? "date" : numeric ? "number" : "text"

            }

            step={

               definition.data_type === "number"

                  ? 1

                  : definition.precision == null

                     ? "any"

                     : 10 ** -definition.precision

            }

            min={definition.min_value ?? undefined}

            max={definition.max_value ?? undefined}

            value={String(value ?? "")}

            onChange={(e) =>

               onChange(

                  numeric

                     ? e.target.value

                     : e.target.value,

               )

            }

         />

         {hint}

      </label>

   );

}



function formatSpecification(value: unknown) {

   if (Array.isArray(value)) return value.join(", ");

   if (value && typeof value === "object") {

      const measurement = value as { amount?: unknown; unit?: unknown };

      if (measurement.amount !== undefined)

         return [measurement.amount, measurement.unit].filter(Boolean).join(" ");

      return JSON.stringify(value);

   }

   if (typeof value === "boolean") return value ? "Yes" : "No";

   return String(value ?? "");

}



function formatFileSize(bytes: number) {

   if (bytes < 1024) return `${bytes} B`;

   if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;

   return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;

}



function mergeUniqueFiles(current: File[], incoming: File[]) {

   return [...current, ...incoming].filter(

      (file, index, files) =>

         index ===

         files.findIndex(

            (candidate) =>

               candidate.name === file.name &&

               candidate.size === file.size &&

               candidate.lastModified === file.lastModified,

         ),

   );

}



export default function ProductDetailPage() {

   const { id, workspace = "lighting" } = useParams();

   const { user } = useAuth();

   const nav = useNavigate();
   const [searchParams, setSearchParams] = useSearchParams();
   const requestedVariantId = searchParams.get("model") || "";

   const [family, setFamily] = useState<ProductFamily>();

   const [variantId, setVariantId] = useState("");

   const [mediaId, setMediaId] = useState("");

   const [variantOpen, setVariantOpen] = useState(false);

   const [editingVariant, setEditingVariant] = useState(false);

   const [familyOpen, setFamilyOpen] = useState(false);

   const [familyForm, setFamilyForm] = useState({

      name: "",

      brand: "",

      short_description: "",

      full_description: "",

      features: "",

      applications: "",

      suitability_guidance: "",

      status: "ACTIVE",

   });

   const [fullscreen, setFullscreen] = useState(false);

   const [stockOpen, setStockOpen] = useState(false);

   const [mediaOpen, setMediaOpen] = useState(false);

   const [variantForm, setVariantForm] = useState(variantInitial);

   const [priceHistory,setPriceHistory]=useState<PriceHistory[]>([]);

   const [priceOpen,setPriceOpen]=useState(false);

   const [priceForm,setPriceForm]=useState({price_type:'BASE',amount:0,currency:'INR',tax_inclusive:false,effective_from:'',effective_until:'',status:'APPROVED',approval_note:''});

   const [stock, setStock] = useState({

      quantity: 0,

      reason: "Manual admin adjustment",

   });

   const [upload, setUpload] = useState<{

      files: File[];

      alt_text: string;

      caption: string;

      is_primary: boolean;

   }>({ files: [], alt_text: "", caption: "", is_primary: false });

   const [uploadProgress, setUploadProgress] = useState({

      active: false,

      completed: 0,

      total: 0,

   });

   const [uploadDragActive, setUploadDragActive] = useState(false);

   const [uploadError, setUploadError] = useState("");

   const uploadInputRef = useRef<HTMLInputElement | null>(null);

   const uploadAbort = useRef<AbortController | null>(null);

   const [notice, setNotice] = useState<{

      kind: "success" | "error";

      text: string;

   }>();

   const [specDefinitions, setSpecDefinitions] = useState<SpecDefinition[]>([]);

   const [specDefinitionsReady, setSpecDefinitionsReady] = useState(false);

   const [variantError, setVariantError] = useState("");



   const load = async () => {

      try {

         const value = await api<ProductFamily>(`/api/v1/product-families/${id}`);

         setFamily(value);

         setVariantId((current) => {
            if (requestedVariantId && value.variants?.some((item) => item.id === requestedVariantId)) {
               return requestedVariantId;
            }
            return value.variants?.some((item) => item.id === current) ? current : "";
         });

      } catch (first: any) {

         try {

            const product = await api<Product>(`/api/v1/products/${id}`);

            if (product.family_id) {

               const value = await api<ProductFamily>(

                  `/api/v1/product-families/${product.family_id}`,

               );

               setFamily(value);
               setVariantId(product.id);
               setSearchParams({ model: product.id }, { replace: true });

            } else

               setFamily({

                  id: product.id,

                  workspace: product.workspace,

                  category_id: product.category_id,

                  category: product.category,

                  name: product.name,

                  slug: product.id,

                  brand: product.brand,

                  short_description: product.description,

                  features: product.features || [],

                  applications: product.applications || [],

                  status: product.status,

                  variant_count: 1,

                  available: product.available,

                  availability: product.available > 0 ? "IN_STOCK" : "OUT_OF_STOCK",

                  primary_image_url: product.primary_image_url,

                  media: product.media || [],

                  variants: [product],

               });

         } catch {

            setNotice({ kind: "error", text: first.message });

         }

      }

   };

   useEffect(() => {
      load();
   }, [id, requestedVariantId]);

   useEffect(() => {

      if (family?.category_id) {

         setSpecDefinitionsReady(false);

         api<any[]>(

            `/api/v1/specification-definitions?workspace=${family.workspace}&category_id=${family.category_id}&family_id=${family.id}`,

         )

            .then((definitions) => { setSpecDefinitions(definitions); setSpecDefinitionsReady(true); })

            .catch(() => { setSpecDefinitions([]); setSpecDefinitionsReady(false); });

      }

   }, [family?.category_id, family?.id, family?.workspace]);

   const variant = family?.variants?.find((item) => item.id === variantId);

   const isModelDetail = Boolean(requestedVariantId && variant);

   const openModel = (modelId: string) => {
      setVariantId(modelId);
      setSearchParams({ model: modelId });
      window.scrollTo({ top: 0, behavior: "smooth" });
   };

   const backToModels = () => {
      setSearchParams({});
      setVariantId("");
      setMediaId("");
      window.scrollTo({ top: 0, behavior: "smooth" });
   };

   useEffect(()=>{

      if(!variant?.id||!(user?.role==='ADMIN'||user?.role==='SUPER_ADMIN')){setPriceHistory([]);return}

      api<PriceHistory[]>(`/api/v1/product-variants/${variant.id}/prices`).then(setPriceHistory).catch(()=>setPriceHistory([]))

   },[variant?.id,user?.role]);

   const displayedSpecs = specDefinitions

      .map((definition) => ({

         definition,

         value: variant?.specs?.[definition.spec_key],

      }))

      .filter(

         ({ value }) => value !== undefined && value !== "" && value !== null,

      );

   const media = useMemo(() => {

      if (!family) return [];

      const all = variant?.media?.length ? variant.media : family.media;

      return all

         .filter(

            (item, index) =>

               all.findIndex((other) => other.id === item.id) === index,

         )

         .sort(

            (a, b) =>

               Number(b.is_primary) - Number(a.is_primary) ||

               a.sort_order - b.sort_order,

         );

   }, [family, variant]);

   const activeMedia = media.find((item) => item.id === mediaId) || media[0];

   useEffect(() => setMediaId(media[0]?.id || ""), [variantId, family?.id]);



   if (!family && !notice)

      return <div className="loading">Loading product family...</div>;

   if (!family)

      return (

         <Card>

            <Empty

               text={notice?.text || "Product family not found."}

               action={

                  <Button onClick={() => nav(`/app/${workspace}/products`)}>

                     Back to catalogue

                  </Button>

               }

            />

         </Card>

      );

   const createVariant = async () => {

      try {

         if (!specDefinitionsReady) throw new Error("Specification fields are still loading. Please try again.");

         setVariantError("");

         const created = await post<Product>(

            `/api/v1/product-families/${family.id}/variants`,

            buildVariantPayload(variantForm, specDefinitions, false),

         );

         setVariantOpen(false);

         setVariantForm({ ...variantInitial, name: family.name });

         setNotice({

            kind: "success",

            text: `Variant ${created.sku} was created.`,

         });

         await load();

         setVariantId(created.id);

      } catch (e: any) {

         setVariantError(e.message);

         setNotice({ kind: "error", text: e.message });

      }

   };

   const saveVariant = async () => {

      if (!variant) return;

      try {

         if (!specDefinitionsReady) throw new Error("Specification fields are still loading. Please try again.");

         setVariantError("");

         await patch(`/api/v1/product-variants/${variant.id}`, buildVariantPayload(variantForm, specDefinitions, true));

         setVariantOpen(false);

         setNotice({ kind: "success", text: `Variant ${variant.sku} updated.` });

         await load();

      } catch (e: any) {

         setVariantError(e.message);

         setNotice({ kind: "error", text: e.message });

      }

   };

   const openVariantEdit = () => {

      if (!variant) return;

      setEditingVariant(true);

      setVariantForm({

         sku: variant.sku,

         name: variant.name,

         internal_name: variant.internal_name || "",

         variant_name: variant.variant_name || "",

         model_number: variant.model_number || "",

         barcode: variant.barcode || "",

         manufacturer: variant.manufacturer || "",

         search_tags: (variant.search_tags||[]).join(', '),

         description: variant.description || "",

         full_description: variant.full_description || "",

         highlights: (variant.highlights||[]).join('\n'),

         features: (variant.features||[]).join('\n'),

         applications: (variant.applications||[]).join('\n'),

         installation_summary: variant.installation_summary || "",

         care_guide: variant.care_guide || "",

         warranty_summary: variant.warranty_summary || "",

         internal_notes: variant.internal_notes || "",

         unit: variant.unit,

         price: String(variant.price ?? 0),

         cost: variant.cost == null ? "" : String(variant.cost),

         mrp_price: variant.mrp_price == null ? "" : String(variant.mrp_price),

         project_price: variant.project_price == null ? "" : String(variant.project_price),

         dealer_price: variant.dealer_price == null ? "" : String(variant.dealer_price),

         reseller_price: variant.reseller_price == null ? "" : String(variant.reseller_price),

         currency: variant.currency || 'INR',

         minimum_order_quantity: String(variant.minimum_order_quantity ?? 1),

         pricing_status: variant.pricing_status || 'DRAFT',

         tax_rate: String(variant.tax_rate),

         on_hand: String(variant.on_hand ?? 0),

         reorder_level: String(variant.reorder_level ?? 0),

         hsn_sac: variant.hsn_sac || "",

         lead_time_days: variant.lead_time_days == null ? "" : String(variant.lead_time_days),

         warranty: variant.warranty || "",

         specs: { ...variant.specs },

      });

      setVariantOpen(true);

   };

   const openFamilyEdit = () => {

      setFamilyForm({

         name: family.name,

         brand: family.brand,

         short_description: family.short_description || "",

         full_description: family.full_description || "",

         features: family.features.join("\n"),

         applications: family.applications.join("\n"),

         suitability_guidance: family.suitability_guidance || "",

         status: family.status,

      });

      setFamilyOpen(true);

   };

   const saveFamily = async () => {

      try {

         await patch(`/api/v1/product-families/${family.id}`, {

            ...familyForm,

            features: familyForm.features

               .split("\n")

               .map((x) => x.trim())

               .filter(Boolean),

            applications: familyForm.applications

               .split("\n")

               .map((x) => x.trim())

               .filter(Boolean),

         });

         setFamilyOpen(false);

         setNotice({ kind: "success", text: "Product family updated." });

         await load();

      } catch (e: any) {

         setNotice({ kind: "error", text: e.message });

      }

   };

   const updateActiveMedia = async (values: Record<string, unknown>) => {

      if (!activeMedia) return;

      try {

         await patch(`/api/v1/product-media/${activeMedia.id}`, values);

         await load();

      } catch (e: any) {

         setNotice({ kind: "error", text: e.message });

      }

   };

   const addScheduledPrice=async()=>{

      if(!variant)return;

      try{await post(`/api/v1/product-variants/${variant.id}/prices`,{...priceForm,effective_from:priceForm.effective_from||null,effective_until:priceForm.effective_until||null,approval_note:priceForm.approval_note||null});setPriceOpen(false);setNotice({kind:'success',text:'Price history entry saved.'});setPriceHistory(await api<PriceHistory[]>(`/api/v1/product-variants/${variant.id}/prices`));await load()}catch(e:any){setNotice({kind:'error',text:e.message})}

   };

   const removeActiveMedia = async () => {

      if (!activeMedia) return;

      try {

         await del(`/api/v1/product-media/${activeMedia.id}`);

         setNotice({ kind: "success", text: "Product image removed." });

         await load();

      } catch (e: any) {

         setNotice({ kind: "error", text: e.message });

      }

   };

   const adjustStock = async () => {

      if (!variant) return;

      try {

         await post(`/api/v1/products/${variant.id}/stock`, stock);

         setStockOpen(false);

         setStock({ quantity: 0, reason: "Manual admin adjustment" });

         setNotice({ kind: "success", text: "Stock was updated and logged." });

         await load();

      } catch (e: any) {

         setNotice({ kind: "error", text: e.message });

      }

   };

   const uploadMedia = async () => {

      if (!variant || !upload.files.length) return;

      setUploadError("");

      const controller = new AbortController();

      uploadAbort.current = controller;

      setUploadProgress({

         active: true,

         completed: 0,

         total: upload.files.length,

      });

      let completed = 0;

      try {

         for (const [index, file] of upload.files.entries()) {

            const body = new FormData();

            body.append("file", file);

            body.append("alt_text", upload.alt_text || file.name);

            if (upload.caption) body.append("caption", upload.caption);

            body.append("is_primary", String(upload.is_primary && index === 0));

            await api<ProductMedia>(

               `/api/v1/product-variants/${variant.id}/media`,

               { method: "POST", body, signal: controller.signal },

            );

            setUploadProgress({

               active: true,

               completed: index + 1,

               total: upload.files.length,

            });

            completed = index + 1;

         }

         // Keep the completed state visible long enough to confirm every file.

         await new Promise((resolve) => window.setTimeout(resolve, 900));

         setMediaOpen(false);

         setUpload({ files: [], alt_text: "", caption: "", is_primary: false });

         setUploadProgress({ active: false, completed: 0, total: 0 });

         setNotice({ kind: "success", text: "Product images uploaded." });

         await load();

      } catch (e: any) {

         if (completed)

            setUpload((current) => ({

               ...current,

               files: current.files.slice(completed),

            }));

         const message =

            e.name === "AbortError"

               ? "Image upload cancelled. Completed files were retained."

               : `${e.message} Keep the remaining selection and choose Retry Upload.`;

         setUploadError(message);

         setNotice({ kind: "error", text: message });

      } finally {

         uploadAbort.current = null;

         setUploadProgress((current) => ({ ...current, active: false }));

      }

   };



   return (
      <>
         <Breadcrumbs
            items={[
               { label: "Product Catalogue", to: `/app/${workspace}/products` },
               { label: family.category, to: `/app/${workspace}/products` },
               { label: family.name },
               ...(isModelDetail && variant
                  ? [{ label: variant.variant_name || variant.name || variant.sku }]
                  : []),
            ]}
         />

         <PageTitle
            title={isModelDetail && variant ? variant.variant_name || variant.name || family.name : family.name}
            subtitle={
               isModelDetail && variant
                  ? `${family.name} · ${family.brand} · ${variant.model_number || variant.sku}`
                  : `${family.brand} · ${family.category}`
            }
            badge={family.workspace}
            actions={
               <>
                  {isModelDetail ? (
                     <Button variant="secondary" onClick={backToModels}>
                        <ArrowLeft size={16} /> All Models
                     </Button>
                  ) : (
                     <Button variant="secondary" onClick={() => nav(`/app/${workspace}/products`)}>
                        <ArrowLeft size={16} /> Catalogue
                     </Button>
                  )}

                  {(user?.role === "ADMIN" || user?.role === "SUPER_ADMIN") && !isModelDetail && (
                     <Button variant="secondary" onClick={openFamilyEdit}>
                        <Pencil size={16} /> Edit Family
                     </Button>
                  )}

                  {(user?.role === "ADMIN" || user?.role === "SUPER_ADMIN") && !isModelDetail && (
                     <Button
                        onClick={() => {
                           setEditingVariant(false);
                           setVariantForm({ ...variantInitial, name: family.name });
                           setVariantOpen(true);
                        }}
                     >
                        <PackagePlus size={16} /> Add Variant
                     </Button>
                  )}

                  {(user?.role === "ADMIN" || user?.role === "SUPER_ADMIN") && isModelDetail && variant && (
                     <Button onClick={openVariantEdit}>
                        <Pencil size={16} /> Edit Model
                     </Button>
                  )}
               </>
            }
         />

         {notice && <Notice kind={notice.kind}>{notice.text}</Notice>}

         {!isModelDetail ? (
            <section className="family-model-browser">
               <div className="family-model-intro">
                  <div>
                     <span className="product-section-kicker">Available models</span>
                     <h2>Select a product model</h2>
                     <p>
                        Choose a model to open its dedicated product page with images,
                        specifications, availability and commercial information.
                     </p>
                  </div>
                  <span className="model-count">
                     {family.variants?.length || 0} {(family.variants?.length || 0) === 1 ? "model" : "models"}
                  </span>
               </div>

               {!family.variants?.length ? (
                  <Card>
                     <Empty text="No sellable variants have been created." />
                  </Card>
               ) : (
                  <div className="family-model-grid">
                     {family.variants.map((item) => {
                        const previewSpecs = specDefinitions
                           .map((definition) => ({
                              definition,
                              value: item.specs?.[definition.spec_key],
                           }))
                           .filter(({ value }) => value !== undefined && value !== "" && value !== null)
                           .slice(0, 4);

                        return (
                           <button
                              key={item.id}
                              type="button"
                              className="family-model-card"
                              onClick={() => openModel(item.id)}
                           >
                              <div className="family-model-image">
                                 <ProductImage family={family} product={item} size={360} />
                              </div>

                              <div className="family-model-card-body">
                                 <div className="family-model-card-topline">
                                    <span>{item.model_number || item.sku}</span>
                                    <Status value={item.available > 0 ? "IN_STOCK" : "OUT_OF_STOCK"} />
                                 </div>

                                 <h3>{item.variant_name || item.name}</h3>
                                 <p className="family-model-sku">SKU: {item.sku}</p>

                                 {previewSpecs.length > 0 && (
                                    <div className="family-model-specs">
                                       {previewSpecs.map(({ definition, value }) => (
                                          <div key={definition.spec_key}>
                                             <span>{definition.label}</span>
                                             <strong>{formatSpecification(value)}</strong>
                                          </div>
                                       ))}
                                    </div>
                                 )}

                                 <div className="family-model-open">
                                    View product details <span aria-hidden="true">→</span>
                                 </div>
                              </div>
                           </button>
                        );
                     })}
                  </div>
               )}
            </section>
         ) : variant ? (
            <>
               <div className="model-detail-toolbar">
                  <button type="button" className="model-detail-back" onClick={backToModels}>
                     <ArrowLeft size={17} /> Back to all {family.name} models
                  </button>
               </div>

               <div className="selected-product-shell standalone-product-page">
                  <section className="selected-product-media">
                     <div className="product-image-stage">
                        {activeMedia ? (
                           <button
                              type="button"
                              className="product-image-zoom"
                              onClick={() => setFullscreen(true)}
                              aria-label="View full-size image"
                           >
                              <img
                                 src={activeMedia.url}
                                 alt={activeMedia.alt_text || variant.variant_name || variant.name}
                              />
                              <span className="product-zoom-indicator">
                                 <Maximize2 size={18} /> View image
                              </span>
                           </button>
                        ) : (
                           <div className="product-image-placeholder">
                              <ProductImage family={family} product={variant} size={560} />
                           </div>
                        )}
                     </div>

                     {media.length > 1 && (
                        <div className="product-thumbnail-strip">
                           {media.map((item, index) => (
                              <button
                                 type="button"
                                 key={item.id}
                                 className={`product-thumbnail ${activeMedia?.id === item.id ? "active" : ""}`}
                                 onClick={() => setMediaId(item.id)}
                                 aria-label={`View image ${index + 1}`}
                              >
                                 <img src={item.url} alt={item.alt_text || `${family.name} image ${index + 1}`} />
                                 {item.is_primary && <span className="primary-image-badge">Primary</span>}
                              </button>
                           ))}
                        </div>
                     )}

                     {(user?.role === "ADMIN" || user?.role === "SUPER_ADMIN") && (
                        <div className="product-image-admin">
                           <Button
                              variant="secondary"
                              onClick={() => {
                                 setUpload({
                                    ...upload,
                                    alt_text: `${family.name} ${variant.variant_name || variant.sku}`,
                                 });
                                 setMediaOpen(true);
                              }}
                           >
                              <ImagePlus size={16} /> Upload Images
                           </Button>

                           {activeMedia && (
                              <>
                                 <Button
                                    variant="secondary"
                                    onClick={() =>
                                       updateActiveMedia({ sort_order: Math.max(0, activeMedia.sort_order - 1) })
                                    }
                                 >
                                    Move Earlier
                                 </Button>
                                 <Button
                                    variant="secondary"
                                    onClick={() => updateActiveMedia({ sort_order: activeMedia.sort_order + 1 })}
                                 >
                                    Move Later
                                 </Button>
                                 {!activeMedia.is_primary && (
                                    <Button variant="secondary" onClick={() => updateActiveMedia({ is_primary: true })}>
                                       <Star size={15} /> Make Primary
                                    </Button>
                                 )}
                                 <Button variant="danger" onClick={removeActiveMedia}>
                                    <Trash2 size={15} /> Delete
                                 </Button>
                              </>
                           )}
                        </div>
                     )}
                  </section>

                  <section className="selected-product-content">
                     <div className="selected-product-header">
                        <div className="selected-product-heading">
                           <div className="selected-product-meta-line">
                              <span className="product-brand">{family.brand}</span>
                              <span className="product-category">{family.category}</span>
                           </div>

                           <h1>{variant.variant_name || variant.name || family.name}</h1>

                           <div className="product-reference-row">
                              {variant.model_number && <span>Model {variant.model_number}</span>}
                              <span>SKU {variant.sku}</span>
                           </div>

                           <p className="selected-product-description">
                              {variant.full_description ||
                                 variant.description ||
                                 family.full_description ||
                                 family.short_description ||
                                 "No product description has been provided."}
                           </p>
                        </div>

                        <div className="selected-product-status">
                           <Status value={variant.status} />
                           <Status value={variant.available > 0 ? "IN_STOCK" : "OUT_OF_STOCK"} />
                        </div>
                     </div>

                     <div className="product-information-grid">
                        <div className="product-information-item">
                           <span>Model</span>
                           <strong>{variant.model_number || variant.variant_name || "—"}</strong>
                        </div>
                        <div className="product-information-item">
                           <span>SKU</span>
                           <strong>{variant.sku || "—"}</strong>
                        </div>
                        <div className="product-information-item">
                           <span>Unit</span>
                           <strong>{variant.unit || "—"}</strong>
                        </div>
                        <div className="product-information-item">
                           <span>Availability</span>
                           <strong>{variant.available ?? 0} {variant.unit}</strong>
                        </div>
                        <div className="product-information-item">
                           <span>Lead time</span>
                           <strong>{variant.lead_time_days == null ? "—" : `${variant.lead_time_days} days`}</strong>
                        </div>
                        <div className="product-information-item">
                           <span>Warranty</span>
                           <strong>{variant.warranty || variant.warranty_summary || "—"}</strong>
                        </div>
                        {variant.manufacturer && (
                           <div className="product-information-item">
                              <span>Manufacturer</span>
                              <strong>{variant.manufacturer}</strong>
                           </div>
                        )}
                        {(user?.role === "ADMIN" || user?.role === "SUPER_ADMIN") && (
                           <>
                              <div className="product-information-item">
                                 <span>Price</span>
                                 <strong>{money(variant.price || 0)}</strong>
                              </div>
                              <div className="product-information-item">
                                 <span>On hand</span>
                                 <strong>{variant.on_hand ?? 0}</strong>
                              </div>
                              <div className="product-information-item">
                                 <span>Reserved</span>
                                 <strong>{variant.reserved ?? 0}</strong>
                              </div>
                           </>
                        )}
                     </div>

                     {(user?.role === "ADMIN" || user?.role === "SUPER_ADMIN") && (
                        <div className="selected-product-actions">
                           <Button variant="secondary" onClick={openVariantEdit}>
                              <Pencil size={15} /> Edit Product
                           </Button>
                           <Button variant="secondary" onClick={() => setStockOpen(true)}>
                              <PackagePlus size={16} /> Adjust Stock
                           </Button>
                        </div>
                     )}

                     {((variant.features?.length || 0) > 0 || family.features.length > 0) && (
                        <div className="product-content-section">
                           <h3>Key Features</h3>
                           <ul className="product-feature-list">
                              {(variant.features?.length ? variant.features : family.features).map((item) => (
                                 <li key={item}>
                                    <CheckCircle2 size={17} />
                                    <span>{item}</span>
                                 </li>
                              ))}
                           </ul>
                        </div>
                     )}

                     {((variant.applications?.length || 0) > 0 || family.applications.length > 0) && (
                        <div className="product-content-section">
                           <h3>Applications</h3>
                           <div className="product-application-list">
                              {(variant.applications?.length ? variant.applications : family.applications).map((item) => (
                                 <span key={item}>{item}</span>
                              ))}
                           </div>
                        </div>
                     )}

                     <div className="product-specifications-section">
                        <div className="product-subsection-heading">
                           <div>
                              <span>Technical data</span>
                              <h2>Technical specifications</h2>
                           </div>
                           <span className="specification-count">{displayedSpecs.length}</span>
                        </div>

                        {displayedSpecs.length ? (
                           <div className="product-spec-grid">
                              {displayedSpecs.map(({ definition, value }) => (
                                 <div className="product-spec-item" key={definition.spec_key}>
                                    <span className="product-spec-label">{definition.label}</span>
                                    <span className="product-spec-value">{formatSpecification(value)}</span>
                                 </div>
                              ))}
                           </div>
                        ) : (
                           <div className="product-spec-empty">
                              No specifications have been recorded for this model.
                           </div>
                        )}
                     </div>
                  </section>
               </div>

               {(user?.role === "ADMIN" || user?.role === "SUPER_ADMIN") && (
                  <Card className="product-pricing-history">
                     <div className="product-section-heading">
                        <div>
                           <span className="product-section-kicker">Administration</span>
                           <h2>Pricing history</h2>
                           <p>Approved effective-dated prices are retained as immutable commercial history.</p>
                        </div>
                        <Button
                           variant="secondary"
                           onClick={() => {
                              setPriceForm((current) => ({ ...current, currency: variant.currency || "INR" }));
                              setPriceOpen(true);
                           }}
                        >
                           Add Scheduled Price
                        </Button>
                     </div>

                     {priceHistory.length ? (
                        <div className="responsive-table">
                           <table>
                              <thead>
                                 <tr>
                                    <th>Type</th>
                                    <th>Amount</th>
                                    <th>Effective</th>
                                    <th>Until</th>
                                    <th>Status</th>
                                 </tr>
                              </thead>
                              <tbody>
                                 {priceHistory.map((item) => (
                                    <tr key={item.id}>
                                       <td>{item.price_type}</td>
                                       <td>{item.currency} {item.amount.toFixed(2)}</td>
                                       <td>{new Date(item.effective_from).toLocaleString()}</td>
                                       <td>{item.effective_until ? new Date(item.effective_until).toLocaleString() : "Current"}</td>
                                       <td><Status value={item.status} /></td>
                                    </tr>
                                 ))}
                              </tbody>
                           </table>
                        </div>
                     ) : (
                        <Empty text="No pricing history has been recorded yet." />
                     )}
                  </Card>
               )}
            </>
         ) : (
            <Card>
               <Empty text="The selected model could not be found." action={<Button onClick={backToModels}>Back to models</Button>} />
            </Card>
         )}

         <Modal

            open={priceOpen}

            title={`Add Price History · ${variant?.sku||''}`}

            onClose={()=>setPriceOpen(false)}

            footer={<><Button variant="secondary" onClick={()=>setPriceOpen(false)}>Cancel</Button><Button disabled={priceForm.amount<0} onClick={addScheduledPrice}>Save price</Button></>}

         >

            <div className="form-grid two"><label>Price type<select value={priceForm.price_type} onChange={e=>setPriceForm(current=>({...current,price_type:e.target.value}))}><option>BASE</option><option>MRP</option><option>PROJECT</option><option>DEALER</option><option>RESELLER</option><option>COST</option></select></label><label>Amount<input type="number" min="0" step="0.01" value={priceForm.amount} onChange={e=>setPriceForm(current=>({...current,amount:Number(e.target.value)}))}/></label><label>Currency<input maxLength={3} value={priceForm.currency} onChange={e=>setPriceForm(current=>({...current,currency:e.target.value.toUpperCase()}))}/></label><label>Status<select value={priceForm.status} onChange={e=>setPriceForm(current=>({...current,status:e.target.value}))}><option>APPROVED</option><option>PENDING_APPROVAL</option><option>DRAFT</option><option>REJECTED</option></select></label><label>Effective from<input type="datetime-local" value={priceForm.effective_from} onChange={e=>setPriceForm(current=>({...current,effective_from:e.target.value}))}/></label><label>Effective until<input type="datetime-local" value={priceForm.effective_until} onChange={e=>setPriceForm(current=>({...current,effective_until:e.target.value}))}/></label><label className="checkbox-row"><input type="checkbox" checked={priceForm.tax_inclusive} onChange={e=>setPriceForm(current=>({...current,tax_inclusive:e.target.checked}))}/> Tax inclusive</label><label className="span-2">Approval note<textarea value={priceForm.approval_note} onChange={e=>setPriceForm(current=>({...current,approval_note:e.target.value}))}/></label></div>

         </Modal>

         <Modal

            open={variantOpen}

            title={`${editingVariant ? "Edit" : "Add"} Variant · ${family.name}`}

            onClose={() => setVariantOpen(false)}

            footer={

               <>

                  <Button variant="secondary" onClick={() => setVariantOpen(false)}>

                     Cancel

                  </Button>

                  <Button

                     disabled={!variantForm.sku.trim() || !variantForm.name.trim()}

                     onClick={editingVariant ? saveVariant : createVariant}

                  >

                     {editingVariant ? "Save Variant" : "Create Variant"}

                  </Button>

               </>

            }

         >

            {variantError && <div role="alert" className="form-error">{variantError}</div>}

            <div className="form-grid two">

               <label>

                  SKU *

                  <input

                     disabled={editingVariant}

                     value={variantForm.sku}

                     onChange={(e) =>

                        setVariantForm({ ...variantForm, sku: e.target.value })

                     }

                  />

               </label>

               <label>

                  Variant name

                  <input

                     value={variantForm.variant_name}

                     onChange={(e) =>

                        setVariantForm({ ...variantForm, variant_name: e.target.value })

                     }

                  />

               </label>

               <label>

                  Model number

                  <input

                     value={variantForm.model_number}

                     onChange={(e) =>

                        setVariantForm({ ...variantForm, model_number: e.target.value })

                     }

                  />

               </label>

               <label>

                  Display name *

                  <input

                     value={variantForm.name}

                     onChange={(e) =>

                        setVariantForm({ ...variantForm, name: e.target.value })

                     }

                  />

               </label>

               <label>

                  Internal name

                  <input value={variantForm.internal_name} onChange={(e)=>setVariantForm(current=>({...current,internal_name:e.target.value}))}/>

               </label>

               <label>

                  Manufacturer

                  <input value={variantForm.manufacturer} onChange={(e)=>setVariantForm(current=>({...current,manufacturer:e.target.value}))}/>

               </label>

               <label>

                  Barcode / reference

                  <input value={variantForm.barcode} onChange={(e)=>setVariantForm(current=>({...current,barcode:e.target.value}))}/>

               </label>

               <label>

                  Search tags <small>(comma separated)</small>

                  <input value={variantForm.search_tags} onChange={(e)=>setVariantForm(current=>({...current,search_tags:e.target.value}))}/>

               </label>

               <label>

                  Unit

                  <input

                     value={variantForm.unit}

                     onChange={(e) =>

                        setVariantForm({ ...variantForm, unit: e.target.value })

                     }

                  />

               </label>

               <label>

                  Price

                  <input

                     type="number"

                     min="0"

                     value={variantForm.price}

                     onChange={(e) =>

                        setVariantForm({

                           ...variantForm,

                           price: e.target.value,

                        })

                     }

                  />

               </label>

               <label>

                  Cost

                  <input

                     type="number"

                     min="0"

                     value={variantForm.cost}

                     onChange={(e) =>

                        setVariantForm({ ...variantForm, cost: e.target.value })

                     }

                  />

               </label>

               <label>MRP / list price<input type="number" min="0" step="0.01" value={variantForm.mrp_price} onChange={e=>setVariantForm(current=>({...current,mrp_price:e.target.value}))}/></label>

               <label>Project price<input type="number" min="0" step="0.01" value={variantForm.project_price} onChange={e=>setVariantForm(current=>({...current,project_price:e.target.value}))}/></label>

               <label>Dealer price<input type="number" min="0" step="0.01" value={variantForm.dealer_price} onChange={e=>setVariantForm(current=>({...current,dealer_price:e.target.value}))}/></label>

               <label>Reseller price<input type="number" min="0" step="0.01" value={variantForm.reseller_price} onChange={e=>setVariantForm(current=>({...current,reseller_price:e.target.value}))}/></label>

               <label>Currency<input maxLength={3} value={variantForm.currency} onChange={e=>setVariantForm(current=>({...current,currency:e.target.value.toUpperCase()}))}/></label>

               <label>Minimum order quantity<input type="number" min="0.01" step="0.01" value={variantForm.minimum_order_quantity} onChange={e=>setVariantForm(current=>({...current,minimum_order_quantity:e.target.value}))}/></label>

               <label>Tax rate (%)<input type="number" min="0" max="100" step="0.01" value={variantForm.tax_rate} onChange={e=>setVariantForm(current=>({...current,tax_rate:e.target.value}))}/></label>

               <label>Pricing status<select value={variantForm.pricing_status} onChange={e=>setVariantForm(current=>({...current,pricing_status:e.target.value}))}><option>DRAFT</option><option>PRICE_REQUIRED</option><option>PENDING_APPROVAL</option><option>APPROVED</option><option>REJECTED</option></select></label>

               {!editingVariant && (

                  <label>

                     Opening stock

                     <input

                        type="number"

                        min="0"

                        value={variantForm.on_hand}

                        onChange={(e) =>

                           setVariantForm({

                              ...variantForm,

                              on_hand: e.target.value,

                           })

                        }

                     />

                  </label>

               )}

               <label>

                  Reorder level

                  <input

                     type="number"

                     min="0"

                     value={variantForm.reorder_level}

                     onChange={(e) =>

                        setVariantForm({

                           ...variantForm,

                           reorder_level: e.target.value,

                        })

                     }

                  />

               </label>

               <label>

                  Lead time (days)

                  <input

                     type="number"

                     min="0"

                     value={variantForm.lead_time_days}

                     onChange={(e) =>

                        setVariantForm({

                           ...variantForm,

                           lead_time_days: e.target.value,

                        })

                     }

                  />

               </label>

               <label>

                  Warranty

                  <input

                     value={variantForm.warranty}

                     onChange={(e) =>

                        setVariantForm({ ...variantForm, warranty: e.target.value })

                     }

                  />

               </label>

               <label className="span-2">

                  Description

                  <textarea

                     value={variantForm.description}

                     onChange={(e) =>

                        setVariantForm({ ...variantForm, description: e.target.value })

                     }

                  />

               </label>

               <label className="span-2">Full description<textarea value={variantForm.full_description} onChange={e=>setVariantForm(current=>({...current,full_description:e.target.value}))}/></label>

               <label>Highlights <small>(one per line)</small><textarea value={variantForm.highlights} onChange={e=>setVariantForm(current=>({...current,highlights:e.target.value}))}/></label>

               <label>Features <small>(one per line)</small><textarea value={variantForm.features} onChange={e=>setVariantForm(current=>({...current,features:e.target.value}))}/></label>

               <label>Applications <small>(one per line)</small><textarea value={variantForm.applications} onChange={e=>setVariantForm(current=>({...current,applications:e.target.value}))}/></label>

               <label>Installation summary<textarea value={variantForm.installation_summary} onChange={e=>setVariantForm(current=>({...current,installation_summary:e.target.value}))}/></label>

               <label>Care guide<textarea value={variantForm.care_guide} onChange={e=>setVariantForm(current=>({...current,care_guide:e.target.value}))}/></label>

               <label>Warranty summary<textarea value={variantForm.warranty_summary} onChange={e=>setVariantForm(current=>({...current,warranty_summary:e.target.value}))}/></label>

               <label className="span-2">Internal notes <small>(administrator only)</small><textarea value={variantForm.internal_notes} onChange={e=>setVariantForm(current=>({...current,internal_notes:e.target.value}))}/></label>

               {specDefinitions.map((definition) => (

                  <SpecificationField

                     key={definition.spec_key}

                     definition={definition}

                     value={variantForm.specs[definition.spec_key]}

                     onChange={(value) =>

                        setVariantForm({

                           ...variantForm,

                           specs: {

                              ...variantForm.specs,

                              [definition.spec_key]: value,

                           },

                        })

                     }

                  />

               ))}

            </div>

         </Modal>

         <Modal

            open={familyOpen}

            title="Edit Product Family"

            onClose={() => setFamilyOpen(false)}

            footer={

               <>

                  <Button variant="secondary" onClick={() => setFamilyOpen(false)}>

                     Cancel

                  </Button>

                  <Button onClick={saveFamily}>Save Family</Button>

               </>

            }

         >

            <div className="form-grid two">

               <label>

                  Name *

                  <input

                     value={familyForm.name}

                     onChange={(e) =>

                        setFamilyForm({ ...familyForm, name: e.target.value })

                     }

                  />

               </label>

               <label>

                  Brand *

                  <input

                     value={familyForm.brand}

                     onChange={(e) =>

                        setFamilyForm({ ...familyForm, brand: e.target.value })

                     }

                  />

               </label>

               <label className="span-2">

                  Short description

                  <textarea

                     value={familyForm.short_description}

                     onChange={(e) =>

                        setFamilyForm({

                           ...familyForm,

                           short_description: e.target.value,

                        })

                     }

                  />

               </label>

               <label className="span-2">

                  Full description

                  <textarea

                     value={familyForm.full_description}

                     onChange={(e) =>

                        setFamilyForm({

                           ...familyForm,

                           full_description: e.target.value,

                        })

                     }

                  />

               </label>

               <label>

                  Features (one per line)

                  <textarea

                     value={familyForm.features}

                     onChange={(e) =>

                        setFamilyForm({ ...familyForm, features: e.target.value })

                     }

                  />

               </label>

               <label>

                  Applications (one per line)

                  <textarea

                     value={familyForm.applications}

                     onChange={(e) =>

                        setFamilyForm({ ...familyForm, applications: e.target.value })

                     }

                  />

               </label>

               <label className="span-2">

                  Suitability guidance

                  <textarea

                     value={familyForm.suitability_guidance}

                     onChange={(e) =>

                        setFamilyForm({

                           ...familyForm,

                           suitability_guidance: e.target.value,

                        })

                     }

                  />

               </label>

               <label>

                  Status

                  <select

                     value={familyForm.status}

                     onChange={(e) =>

                        setFamilyForm({ ...familyForm, status: e.target.value })

                     }

                  >

                     <option>ACTIVE</option>

                     <option>INACTIVE</option>

                  </select>

               </label>

            </div>

         </Modal>

         <Modal

            open={fullscreen}

            title={activeMedia?.alt_text || family.name}

            onClose={() => setFullscreen(false)}

            className="media-fullscreen"

         >

            {activeMedia && (

               <img src={activeMedia.url} alt={activeMedia.alt_text} />

            )}

         </Modal>

         <Modal

            open={stockOpen}

            title={`Adjust Stock · ${variant?.sku || ""}`}

            onClose={() => setStockOpen(false)}

            footer={

               <>

                  <Button variant="secondary" onClick={() => setStockOpen(false)}>

                     Cancel

                  </Button>

                  <Button disabled={!stock.quantity} onClick={adjustStock}>

                     Apply Adjustment

                  </Button>

               </>

            }

         >

            <p className="muted">

               Use a negative quantity to reduce stock. The server prevents negative

               inventory and records every adjustment.

            </p>

            <div className="form-grid two">

               <label>

                  Adjustment

                  <input

                     type="number"

                     value={stock.quantity}

                     onChange={(e) =>

                        setStock({ ...stock, quantity: Number(e.target.value) })

                     }

                  />

               </label>

               <label>

                  Reason

                  <input

                     value={stock.reason}

                     onChange={(e) => setStock({ ...stock, reason: e.target.value })}

                  />

               </label>

            </div>

         </Modal>

         <Modal

            open={mediaOpen}

            title="Upload Product Image"

            onClose={() => {

               if (uploadProgress.active) return;

               setMediaOpen(false);

               setUploadError("");

            }}

            footer={

               <>

                  <Button

                     variant="secondary"

                     onClick={() =>

                        uploadProgress.active

                           ? uploadAbort.current?.abort()

                           : setMediaOpen(false)

                     }

                  >

                     {uploadProgress.active ? "Cancel Upload" : "Cancel"}

                  </Button>

                  <Button

                     disabled={!upload.files.length || uploadProgress.active}

                     onClick={uploadMedia}

                  >

                     <Upload size={16} />

                     {uploadProgress.active

                        ? uploadProgress.completed === uploadProgress.total

                           ? "Uploaded"

                           : "Uploading..."

                        : uploadProgress.completed

                           ? "Retry Upload"

                           : `Upload ${upload.files.length || ""}`.trim()}

                  </Button>

               </>

            }

         >

            <div className="media-upload-intro">

               <span className="media-upload-intro-icon" aria-hidden="true">

                  <Images size={24} />

               </span>

               <div>

                  <h3>Add product gallery images</h3>

                  <p>

                     Upload clear JPG, PNG, or WebP images. Files are decoded and

                     validated securely by the server.

                  </p>

               </div>

            </div>



            <div className="form-grid two media-upload-form">

               <div className="span-2">

                  <span className="media-upload-label">Product images *</span>

                  <div

                     className={`media-drop-zone${uploadDragActive ? " drag-active" : ""}`}

                     onDragEnter={(event) => {

                        event.preventDefault();

                        setUploadDragActive(true);

                     }}

                     onDragOver={(event) => {

                        event.preventDefault();

                        setUploadDragActive(true);

                     }}

                     onDragLeave={(event) => {

                        event.preventDefault();

                        if (event.currentTarget === event.target)

                           setUploadDragActive(false);

                     }}

                     onDrop={(event) => {

                        event.preventDefault();

                        setUploadDragActive(false);

                        const incoming = Array.from(event.dataTransfer.files).filter(

                           (file) =>

                              ["image/jpeg", "image/png", "image/webp"].includes(

                                 file.type,

                              ),

                        );

                        setUpload((current) => ({

                           ...current,

                           files: mergeUniqueFiles(current.files, incoming),

                        }));

                        setUploadError("");

                        setUploadProgress({ active: false, completed: 0, total: 0 });

                     }}

                  >

                     <input

                        ref={uploadInputRef}

                        id="product-media-files"

                        className="media-file-input"

                        type="file"

                        multiple

                        accept="image/jpeg,image/png,image/webp"

                        onChange={(event) => {

                           const incoming = Array.from(event.target.files || []);

                           setUpload((current) => ({

                              ...current,

                              files: mergeUniqueFiles(current.files, incoming),

                           }));

                           setUploadError("");

                           setUploadProgress({ active: false, completed: 0, total: 0 });

                           event.target.value = "";

                        }}

                     />

                     <span className="media-drop-icon" aria-hidden="true">

                        <Upload size={25} />

                     </span>

                     <strong>Drop multiple images here</strong>

                     <span>or choose them from your computer</span>

                     <Button

                        type="button"

                        variant="secondary"

                        disabled={uploadProgress.active}

                        onClick={() => uploadInputRef.current?.click()}

                     >

                        <ImagePlus size={16} /> Choose images

                     </Button>

                     <small>JPG, PNG or WebP · Maximum 8 MB per image</small>

                  </div>

               </div>



               {upload.files.length > 0 && (

                  <div className="span-2 media-file-queue">

                     <div className="media-file-queue-head">

                        <div>

                           <b>{upload.files.length} image(s) ready</b>

                           <small>You can add more files before uploading.</small>

                        </div>

                        {!uploadProgress.active && (

                           <button

                              type="button"

                              className="media-clear-button"

                              onClick={() => {

                                 setUpload((current) => ({ ...current, files: [] }));

                                 setUploadProgress({

                                    active: false,

                                    completed: 0,

                                    total: 0,

                                 });

                              }}

                           >

                              Clear all

                           </button>

                        )}

                     </div>

                     <div className="media-file-list">

                        {upload.files.map((file, index) => (

                           <div

                              className="media-file-row"

                              key={`${file.name}-${file.size}-${file.lastModified}`}

                           >

                              <span className="media-file-icon" aria-hidden="true">

                                 <FileImage size={18} />

                              </span>

                              <span className="media-file-copy">

                                 <b title={file.name}>{file.name}</b>

                                 <small>{formatFileSize(file.size)}</small>

                              </span>

                              {uploadProgress.completed > index ? (

                                 <span className="media-file-complete" title="Uploaded">

                                    <CheckCircle2 size={19} />

                                 </span>

                              ) : (

                                 <button

                                    type="button"

                                    className="media-file-remove"

                                    aria-label={`Remove ${file.name}`}

                                    disabled={uploadProgress.active}

                                    onClick={() =>

                                       setUpload((current) => ({

                                          ...current,

                                          files: current.files.filter(

                                             (_, fileIndex) => fileIndex !== index,

                                          ),

                                       }))

                                    }

                                 >

                                    <Trash2 size={16} />

                                 </button>

                              )}

                           </div>

                        ))}

                     </div>

                  </div>

               )}



               <label>

                  Shared alternative text (file name is used when blank)

                  <input

                     value={upload.alt_text}

                     onChange={(e) =>

                        setUpload({ ...upload, alt_text: e.target.value })

                     }

                  />

               </label>

               <label>

                  Caption

                  <input

                     value={upload.caption}

                     onChange={(e) =>

                        setUpload({ ...upload, caption: e.target.value })

                     }

                  />

               </label>

               <label className="checkbox-row">

                  <input

                     type="checkbox"

                     checked={upload.is_primary}

                     onChange={(e) =>

                        setUpload({ ...upload, is_primary: e.target.checked })

                     }

                  />{" "}

                  Make primary image

               </label>

               {uploadError && (

                  <div className="span-2 media-upload-error" role="alert">

                     {uploadError}

                  </div>

               )}

               {(upload.files.length > 0 || uploadProgress.total > 0) && (

                  <div className="span-2 upload-progress" aria-live="polite">

                     <div className="upload-progress-head">

                        <b>

                           {uploadProgress.active

                              ? "Uploading product images"

                              : uploadProgress.completed === uploadProgress.total &&

                                    uploadProgress.total > 0

                                 ? "Upload complete"

                                 : "Ready to upload"}

                        </b>

                        <strong>

                           {uploadProgress.completed} /{" "}

                           {uploadProgress.total || upload.files.length}

                        </strong>

                     </div>

                     <progress

                        max={uploadProgress.total || upload.files.length}

                        value={uploadProgress.completed}

                     />

                     <small>

                        {uploadProgress.completed} of{" "}

                        {uploadProgress.total || upload.files.length} uploaded

                     </small>

                  </div>

               )}

            </div>

         </Modal>

      </>

   );

}
