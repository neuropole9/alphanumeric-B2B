import { useMemo, useState } from "react";
import { Lightbulb, Search } from "lucide-react";
import {
  Button,
  Empty,
  Modal,
  ProductImage,
  Status,
} from "../../components/UI";
import type { Product, Workspace } from "../../types";
import type { WizardData, WizardRequirement } from "./inquiryWizard.types";

type Scope = "room" | "same" | "floor" | "selected";
type Props = {
  open: boolean;
  onClose: () => void;
  products: Product[];
  application: Workspace;
  data: WizardData;
  floorIndex: number;
  roomIndex: number;
  onApply: (targets: Array<[number, number]>, req: WizardRequirement) => void;
};

export default function ProductPickerModal({
  open,
  onClose,
  products,
  application,
  data,
  floorIndex,
  roomIndex,
  onApply,
}: Props) {
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [selected, setSelected] = useState("");
  const [qty, setQty] = useState(1);
  const [notes, setNotes] = useState("");
  const [scope, setScope] = useState<Scope>("room");
  const [selectedRooms, setSelectedRooms] = useState<string[]>([]);
  const isolatedProducts = useMemo(
    () => products.filter((p) => p.workspace === application),
    [products, application],
  );
  const cats = useMemo(
    () => Array.from(new Set(isolatedProducts.map((p) => p.category))).sort(),
    [isolatedProducts],
  );
  const shown = isolatedProducts.filter(
    (p) =>
      (!category || p.category === category) &&
      (!q ||
        `${p.name} ${p.sku} ${p.model_number || ""} ${p.variant_name || ""} ${p.brand}`
          .toLowerCase()
          .includes(q.toLowerCase())),
  );
  const room = data.floors[floorIndex]?.rooms[roomIndex];
  const product = isolatedProducts.find((item) => item.id === selected);
  const targets = (): Array<[number, number]> => {
    if (scope === "floor")
      return data.floors[floorIndex].rooms.map((_, ri) => [floorIndex, ri]);
    if (scope === "same")
      return data.floors.flatMap(
        (f, fi) =>
          f.rooms
            .map((r, ri) =>
              r.name.trim().toLowerCase() === room.name.trim().toLowerCase()
                ? ([fi, ri] as [number, number])
                : null,
            )
            .filter(Boolean) as Array<[number, number]>,
      );
    if (scope === "selected")
      return data.floors.flatMap(
        (f, fi) =>
          f.rooms
            .map((r, ri) =>
              selectedRooms.includes(r.key)
                ? ([fi, ri] as [number, number])
                : null,
            )
            .filter(Boolean) as Array<[number, number]>,
      );
    return [[floorIndex, roomIndex]];
  };
  const reset = () => {
    setSelected("");
    setQty(1);
    setNotes("");
    setScope("room");
    setSelectedRooms([]);
  };
  const close = () => {
    reset();
    onClose();
  };
  const apply = () => {
    if (!product) return;
    onApply(targets(), { product_id: product.id, quantity: qty, notes });
    close();
  };

  return (
    <Modal
      open={open}
      title={
        product
          ? `Preview · ${product.name}`
          : `Choose a Product · ${room?.name || ""}`
      }
      onClose={close}
      className="product-picker-modal"
      footer={
        product ? (
          <>
            <Button variant="secondary" onClick={() => setSelected("")}>
              Back to Catalogue
            </Button>
            <Button variant="danger" onClick={() => setSelected("")}>
              No, Not Suitable
            </Button>
            <Button
              disabled={
                qty <= 0 || (scope === "selected" && !selectedRooms.length)
              }
              onClick={apply}
            >
              Yes, Add Product
            </Button>
          </>
        ) : (
          <Button variant="secondary" onClick={close}>
            Cancel
          </Button>
        )
      }
    >
      {!product ? (
        <>
          <div className="picker-toolbar">
            <div className="picker-application-lock">
              <Lightbulb size={15} />
              <b>{application}</b>
              <span>
                Inquiry application - other applications are unavailable.
              </span>
            </div>
            <div className="picker-filter-row">
              <label className="picker-search">
                <Search size={17} />
                <input
                  placeholder="Search product, model, SKU, or brand"
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                />
              </label>
              <select
                aria-label="Product category"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                <option value="">All Categories</option>
                {cats.map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
            </div>
          </div>
          {!shown.length ? (
            <Empty
              text={`No ${application.toLowerCase()} products match the selected filters.`}
            />
          ) : (
            <div className="picker-products">
              {shown.map((item) => (
                <button
                  type="button"
                  key={item.id}
                  className="picker-product"
                  onClick={() => setSelected(item.id)}
                >
                  <ProductImage product={item} size={56} />
                  <span className="picker-product-copy">
                    <b>{item.family_name || item.name}</b>
                    <small>
                      {item.variant_name || item.name}
                      {item.model_number ? ` · ${item.model_number}` : ""}
                    </small>
                    <small>
                      {item.category} · {item.sku}
                    </small>
                    <small>
                      {Object.entries(item.specs || {})
                        .slice(0, 3)
                        .map(([key, value]) => `${key}: ${String(value)}`)
                        .join(" · ")}
                    </small>
                  </span>
                  <span
                    className={`system-chip ${item.workspace.toLowerCase()}`}
                  >
                    {item.workspace}
                  </span>
                  <span
                    className={`stock-chip ${item.available > 0 ? "available" : "unavailable"}`}
                  >
                    {item.available > 0
                      ? `${item.available} ${item.unit} available`
                      : "Out of stock"}
                  </span>
                </button>
              ))}
            </div>
          )}
        </>
      ) : (
        <div className="picker-preview">
          <div className="proposal-preview">
            <ProductImage product={product} size={230} />
            <div>
              <span
                className={`system-chip ${product.workspace.toLowerCase()}`}
              >
                {product.workspace}
              </span>
              <h2>{product.name}</h2>
              <h3>{product.variant_name || product.sku}</h3>
              <p>
                {product.description ||
                  "No product description has been recorded."}
              </p>
              <dl className="info-list">
                <div>
                  <dt>SKU</dt>
                  <dd>{product.sku}</dd>
                </div>
                <div>
                  <dt>Category</dt>
                  <dd>{product.category}</dd>
                </div>
                <div>
                  <dt>Availability</dt>
                  <dd>
                    <Status value={product.stock_status} />
                  </dd>
                </div>
              </dl>
            </div>
          </div>
          <div className="suitability-question">
            <Lightbulb size={23} />
            <div>
              <h3>Does this product suit this room?</h3>
              <p>
                Review the exact variant, then choose Yes to add it. Choosing No
                returns to the catalogue without changing the room.
              </p>
            </div>
          </div>
          <div className="picker-config">
            <label>
              Quantity
              <input
                type="number"
                min="1"
                value={qty}
                onChange={(e) => setQty(Math.max(1, Number(e.target.value)))}
              />
            </label>
            <label>
              Apply To
              <select
                value={scope}
                onChange={(e) => setScope(e.target.value as Scope)}
              >
                <option value="room">This Room</option>
                <option value="same">Same Room Across Floors</option>
                <option value="floor">Entire Floor</option>
                <option value="selected">Selected Rooms</option>
              </select>
            </label>
            <label>
              Placement Notes
              <input
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Optional placement note"
              />
            </label>
          </div>
          {scope === "selected" && (
            <div className="selected-room-grid">
              {data.floors.map((f) =>
                f.rooms.map((r) => (
                  <label key={r.key}>
                    <input
                      type="checkbox"
                      checked={selectedRooms.includes(r.key)}
                      onChange={(e) =>
                        setSelectedRooms((current) =>
                          e.target.checked
                            ? [...current, r.key]
                            : current.filter((key) => key !== r.key),
                        )
                      }
                    />
                    <span>
                      {f.name} · {r.name}
                    </span>
                  </label>
                )),
              )}
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}
