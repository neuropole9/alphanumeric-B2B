import { useState } from "react";
import { DoorOpen, Layers3, PackageOpen, Plus, Trash2 } from "lucide-react";
import { Button, Card, Empty, ProductImage } from "../../components/UI";
import type { Product, Workspace } from "../../types";
import type { WizardData, WizardRequirement } from "./inquiryWizard.types";
import ProductPickerModal from "./ProductPickerModal";

export default function StepRoomProducts({
  data,
  setData,
  products,
  application,
}: {
  data: WizardData;
  setData: (d: WizardData) => void;
  products: Product[];
  application?: Workspace;
}) {
  const activeApplication =
    application ||
    products[0]?.workspace ||
    data.portalAccess.application_access[0] ||
    "LIGHTING";
  const [selected, setSelected] = useState<[number, number]>([0, 0]);
  const [picker, setPicker] = useState(false);
  const [fi, ri] = selected;
  const room = data.floors[fi]?.rooms[ri];
  const mutateRoom = (
    fidx: number,
    ridx: number,
    fn: (reqs: WizardRequirement[]) => WizardRequirement[],
  ) => {
    const floors = data.floors.map((f, a) =>
      a === fidx
        ? {
            ...f,
            rooms: f.rooms.map((r, b) =>
              b === ridx ? { ...r, requirements: fn(r.requirements) } : r,
            ),
          }
        : f,
    );
    setData({ ...data, floors });
  };
  const apply = (targets: Array<[number, number]>, req: WizardRequirement) => {
    const next = data.floors.map((f) => ({
      ...f,
      rooms: f.rooms.map((r) => ({
        ...r,
        requirements: r.requirements.map((x) => ({ ...x })),
      })),
    }));
    for (const [a, b] of targets) {
      const list = next[a].rooms[b].requirements;
      const ex = list.find((x) => x.product_id === req.product_id);
      if (ex) {
        ex.quantity += req.quantity;
        if (req.notes) ex.notes = req.notes;
      } else list.push({ ...req });
    }
    setData({ ...data, floors: next });
  };
  const product = (id: string) => products.find((p) => p.id === id);

  return (
    <>
      <div className="room-products-layout">
        <Card className="project-tree">
          <div className="tree-heading">
            <span>
              <Layers3 size={19} />
            </span>
            <div>
              <h3>Project Rooms</h3>
              <p>Select a room to configure</p>
            </div>
          </div>
          <div className="tree-scroll">
            {data.floors.map((f, a) => (
              <div className="tree-floor" key={f.key}>
                <div className="tree-floor-label">
                  <b>{f.name}</b>
                  <small>{f.rooms.length} rooms</small>
                </div>
                {f.rooms.map((r, b) => (
                  <button
                    type="button"
                    key={r.key}
                    className={a === fi && b === ri ? "active" : ""}
                    onClick={() => setSelected([a, b])}
                  >
                    <span>
                      <DoorOpen size={15} />
                      {r.name}
                    </span>
                    <em>
                      {r.requirements.reduce((s, x) => s + x.quantity, 0)}
                    </em>
                  </button>
                ))}
              </div>
            ))}
          </div>
        </Card>
        <Card className="room-products-panel">
          <div className="wizard-surface-head room-products-head">
            <div>
              <span className="eyebrow">
                Step 3 of 5 · {data.floors[fi]?.name} · {activeApplication}
              </span>
              <h2>{room?.name}</h2>
              <p>
                Assign exact {activeApplication.toLowerCase()} variants to this
                room.
              </p>
            </div>
            <Button onClick={() => setPicker(true)}>
              <Plus size={17} /> Add Product
            </Button>
          </div>
          {!room?.requirements.length ? (
            <Empty
              text="No products have been assigned to this room."
              action={
                <Button onClick={() => setPicker(true)}>
                  Add First Product
                </Button>
              }
            />
          ) : (
            <div className="assigned-products">
              <div className="assigned-products-heading">
                <span>Product</span>
                <span>Quantity</span>
                <span aria-hidden="true"></span>
              </div>
              {room.requirements.map((req) => {
                const p = product(req.product_id);
                return (
                  <div className="assigned-product" key={req.product_id}>
                    <div className="assigned-product-main">
                      <ProductImage product={p} size={48} />
                      <span>
                        <b>{p?.name}</b>
                        <small>
                          {p?.variant_name || p?.sku} · {p?.category}
                        </small>
                        <span
                          className={`system-chip ${(p?.workspace || "").toLowerCase()}`}
                        >
                          {p?.workspace}
                        </span>
                        {req.notes && (
                          <small className="product-note">{req.notes}</small>
                        )}
                      </span>
                    </div>
                    <label className="quantity-field">
                      <span>Qty</span>
                      <input
                        type="number"
                        min="1"
                        value={req.quantity}
                        onChange={(e) =>
                          mutateRoom(fi, ri, (x) =>
                            x.map((y) =>
                              y.product_id === req.product_id
                                ? {
                                    ...y,
                                    quantity: Math.max(
                                      1,
                                      Number(e.target.value),
                                    ),
                                  }
                                : y,
                            ),
                          )
                        }
                      />
                    </label>
                    <button
                      type="button"
                      className="remove-product"
                      title="Remove product"
                      onClick={() =>
                        mutateRoom(fi, ri, (x) =>
                          x.filter((y) => y.product_id !== req.product_id),
                        )
                      }
                    >
                      <Trash2 size={17} />
                    </button>
                  </div>
                );
              })}
            </div>
          )}
          {room?.requirements.length ? (
            <div className="room-products-summary">
              <PackageOpen size={17} />
              <span>
                <b>{room.requirements.length}</b> unique products ·{" "}
                <b>{room.requirements.reduce((s, x) => s + x.quantity, 0)}</b>{" "}
                total units
              </span>
            </div>
          ) : null}
        </Card>
      </div>
      <ProductPickerModal
        open={picker}
        onClose={() => setPicker(false)}
        products={products}
        application={activeApplication}
        data={data}
        floorIndex={fi}
        roomIndex={ri}
        onApply={apply}
      />
    </>
  );
}
