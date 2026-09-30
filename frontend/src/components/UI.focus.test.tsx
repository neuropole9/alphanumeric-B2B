// @vitest-environment jsdom
import { Fragment, useEffect, useRef, useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Modal } from "./UI";

type Row = { id: string; value: string };

afterEach(cleanup);

function ProductWorkflowForm({ initialName = "", autosave }: { initialName?: string; autosave?: (value: string) => void }) {
  const [name, setName] = useState(initialName);
  const [family, setFamily] = useState("");
  const [shortDescription, setShortDescription] = useState("");
  const [fullDescription, setFullDescription] = useState("");
  const [specification, setSpecification] = useState("");
  const [price, setPrice] = useState("");
  const [imageAlt, setImageAlt] = useState("");
  const [category, setCategory] = useState("lighting");
  const [extended,setExtended]=useState<Record<string,string>>({});
  const [categories, setCategories] = useState(["lighting", "automation"]);
  const [features, setFeatures] = useState<Row[]>([{ id: "feature-1", value: "Existing feature" }]);
  const mountCount = useRef(0);
  useEffect(() => { mountCount.current += 1; }, []);
  useEffect(() => {
    if (!autosave) return;
    const timer = window.setTimeout(() => autosave(name), 50);
    return () => window.clearTimeout(timer);
  }, [autosave, name]);

  const text = (label: string, value: string, change: (value: string) => void, area = false) => (
    <label>
      {label}
      {area ? <textarea aria-label={label} value={value} onChange={(event) => change(event.target.value)} /> : <input aria-label={label} value={value} onChange={(event) => change(event.target.value)} />}
    </label>
  );

  return (
    <Modal open title="Add Product" onClose={() => undefined}>
      <output aria-label="mount count">{mountCount.current}</output>
      {text("Product name", name, setName)}
      {text("Product family name", family, setFamily)}
      {text("Short description", shortDescription, setShortDescription, true)}
      {text("Full description", fullDescription, setFullDescription, true)}
      {text("Dynamic specification", specification, setSpecification)}
      <label>Selling price<input aria-label="Selling price" inputMode="decimal" value={price} onChange={(event) => setPrice(event.target.value)} /></label>
      {features.map((row) => <label key={row.id}>Feature {row.id}<input aria-label={`Feature ${row.id}`} value={row.value} onChange={(event) => setFeatures((current) => current.map((item) => item.id === row.id ? { ...item, value: event.target.value } : item))} /></label>)}
      <button type="button" onClick={() => setFeatures((current) => [...current, { id: `feature-${current.length + 1}`, value: "" }])}>Add feature</button>
      <button type="button" onClick={() => setFeatures((current) => [...current].reverse())}>Reorder features</button>
      {text("Image alternative text", imageAlt, setImageAlt)}
      {['Internal name','Brand','Manufacturer','Model number','SKU','Barcode','HSN/SAC','Highlights','Applications','Installation summary','Care guide','Warranty information','Internal notes','MRP','Dealer price','Reseller price','Image caption','Document name','Customer invitation message'].map(label=><Fragment key={label}>{text(label,extended[label]||'',value=>setExtended(current=>({...current,[label]:value})),['Highlights','Applications','Installation summary','Care guide','Warranty information','Internal notes','Customer invitation message'].includes(label))}</Fragment>)}
      <label>Category<select aria-label="Category" value={category} onChange={(event) => setCategory(event.target.value)}>{categories.map((item) => <option key={item}>{item}</option>)}</select></label>
      <button type="button" onClick={() => { setCategories((current) => [...current, "architectural"]); setCategory("architectural"); }}>Create category inline</button>
    </Modal>
  );
}

async function typeAndKeepFocus(label: string, value: string) {
  const user = userEvent.setup();
  const input = screen.getByRole("textbox", { name: label });
  await user.click(input);
  await user.type(input, value);
  expect((input as HTMLInputElement).value).toBe(value);
  expect(document.activeElement).toBe(input);
  return input as HTMLInputElement;
}

describe("Modal product-form focus stability", () => {
  it("accepts a complete product name without focus loss or remounting", async () => {
    render(<ProductWorkflowForm />);
    await typeAndKeepFocus("Product name", "COB Luminaire");
    expect(screen.getByLabelText("mount count").textContent).toBe("1");
    expect((screen.getByRole("textbox", { name: "Product family name" }) as HTMLInputElement).value).toBe("");
  });

  it.each([
    ["Product family name", "COB Architectural Family"],
    ["Short description", "High-performance customizable COB luminaire."],
    ["Full description", "A complete description with spaces, punctuation, and details."],
    ["Dynamic specification", "CRI > 90 / 3000K–6500K"],
    ["Image alternative text", "AlphaNumeric CA1 COB luminaire – front view"],
  ])("supports continuous realistic typing in %s", async (label, value) => {
    render(<ProductWorkflowForm />);
    await typeAndKeepFocus(label, value);
  });

  it.each([
    ["Internal name","COB Luminaire Internal Reference"],["Brand","AlphaNumeric Professional"],
    ["Manufacturer","AlphaNumeric Industries Pvt Ltd"],["Model number","CA1-12W-3000K-WH"],
    ["SKU","LIGHT-COB-CA1-12W"],["Barcode","8901234567890"],["HSN/SAC","94054090"],
    ["Highlights","High CRI above 90 with low glare"],["Applications","Retail, hospitality, and offices"],
    ["Installation summary","Install into the specified ceiling cut-out."],["Care guide","Disconnect power and clean with a dry cloth."],
    ["Warranty information","Three-year limited project warranty."],["Internal notes","Approved margin and supplier reference."],
    ["MRP","1800.00"],["Dealer price","1250.00"],["Reseller price","1200.00"],
    ["Image caption","CA1 front view in white finish"],["Document name","CA1 installation and care guide"],
    ["Customer invitation message","Welcome to the secure AlphaNumeric project portal."],
  ])("keeps focus while typing complete extended field %s",async(label,value)=>{render(<ProductWorkflowForm/>);await typeAndKeepFocus(label,value)});

  it("supports rapid typing, Backspace, cursor editing, paste, and Tab navigation", async () => {
    const user = userEvent.setup({ delay: 1 });
    render(<ProductWorkflowForm />);
    const input = screen.getByRole("textbox", { name: "Product name" }) as HTMLInputElement;
    await user.click(input);
    await user.type(input, "COB LuminaireX");
    await user.keyboard("{Backspace}");
    input.setSelectionRange(3, 3);
    await user.keyboard("Premium ");
    await user.paste("Series");
    expect(input.value).toBe("COBPremium Series Luminaire");
    expect(document.activeElement).toBe(input);
    await user.tab();
    expect(document.activeElement).toBe(screen.getByRole("textbox", { name: "Product family name" }));
    await user.tab({ shift: true });
    expect(document.activeElement).toBe(input);
  });

  it("keeps numeric pricing input active for continuous editing", async () => {
    render(<ProductWorkflowForm />);
    const input = await typeAndKeepFocus("Selling price", "625695.50");
    expect(input.value).toBe("625695.50");
  });

  it("preserves stable repeatable rows after add and reorder", async () => {
    const user = userEvent.setup();
    render(<ProductWorkflowForm />);
    await user.click(screen.getByRole("button", { name: "Add feature" }));
    const added = screen.getByRole("textbox", { name: "Feature feature-2" }) as HTMLInputElement;
    await user.type(added, "Tool-free installation");
    expect(document.activeElement).toBe(added);
    await user.click(screen.getByRole("button", { name: "Reorder features" }));
    const reordered = screen.getByRole("textbox", { name: "Feature feature-2" }) as HTMLInputElement;
    expect(reordered).toBe(added);
    expect(reordered.value).toBe("Tool-free installation");
  });

  it("loads edit data once and preserves it while another field changes", async () => {
    render(<ProductWorkflowForm initialName="Existing CA1" />);
    await typeAndKeepFocus("Product family name", "COB");
    expect((screen.getByRole("textbox", { name: "Product name" }) as HTMLInputElement).value).toBe("Existing CA1");
  });

  it("does not autosave on every character or replace the active local edit", async () => {
    const autosave = vi.fn();
    const user = userEvent.setup();
    render(<ProductWorkflowForm autosave={autosave} />);
    const input = screen.getByRole("textbox", { name: "Product name" }) as HTMLInputElement;
    await user.type(input, "COB Luminaire");
    expect(input.value).toBe("COB Luminaire");
    expect(document.activeElement).toBe(input);
    expect(autosave.mock.calls.length).toBeLessThanOrEqual(1);
  });

  it("preserves typing after inline category creation and selection", async () => {
    const user = userEvent.setup();
    render(<ProductWorkflowForm />);
    await user.click(screen.getByRole("button", { name: "Create category inline" }));
    expect((screen.getByRole("combobox", { name: "Category" }) as HTMLSelectElement).value).toBe("architectural");
    await typeAndKeepFocus("Product family name", "Architectural COB");
  });

  it("keeps focus stable at a mobile viewport width", async () => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 390 });
    fireEvent(window, new Event("resize"));
    render(<ProductWorkflowForm />);
    await typeAndKeepFocus("Short description", "Thirty-plus characters entered continuously on mobile.");
  });
});
