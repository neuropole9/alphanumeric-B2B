import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, patch, post } from "../api/client";
import type {
  BuildingDetail,
  Customer,
  Inquiry,
  Product,
  ProjectBuilding,
  ProjectSummary,
} from "../types";
import { Button, Notice, PageTitle } from "../components/UI";
import { ChevronLeft, ChevronRight, Save } from "lucide-react";
import InquiryWizardStepper from "../features/inquiries/InquiryWizardStepper";
import StepProjectClient from "../features/inquiries/StepProjectClient";
import StepProjectStructure from "../features/inquiries/StepProjectStructure";
import StepRoomProducts from "../features/inquiries/StepRoomProducts";
import StepBOQ, { aggregate } from "../features/inquiries/StepBOQ";
import StepReview from "../features/inquiries/StepReview";
import {
  emptyWizard,
  key,
  validateWizard,
  type WizardData,
} from "../features/inquiries/inquiryWizard.types";

export default function CreateInquiryPage() {
  const { workspace = "lighting", id } = useParams();
  const nav = useNavigate();
  const [search] = useSearchParams();
  const [step, setStep] = useState(1);
  const initial = emptyWizard();
  initial.portalAccess.application_access = [
    workspace.toUpperCase() as "LIGHTING" | "AUTOMATION",
  ];
  const [data, setData] = useState<WizardData>(initial);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [buildings, setBuildings] = useState<ProjectBuilding[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [draftId, setDraftId] = useState<string | undefined>(id);
  const [number, setNumber] = useState<string>();
  const [invitationCreated, setInvitationCreated] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{
    kind: "success" | "error" | "warning";
    text: string;
  }>();
  const [loading, setLoading] = useState(Boolean(id));
  const [dirty, setDirty] = useState(false);
  const updateData: typeof setData = (updater) => {
    setDirty(true);
    setData(updater);
  };
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  useEffect(() => {
    Promise.all([
      api<Customer[]>("/api/v1/customers"),
      api<ProjectSummary[]>("/api/v1/projects"),
      api<Product[]>(`/api/v1/products?workspace=${workspace.toUpperCase()}`),
    ])
      .then(([c, p, activeProducts]) => {
        setCustomers(c);
        setProjects(p);
        setProducts(activeProducts);
        setData((current) => ({
          ...current,
          portalAccess: {
            ...current.portalAccess,
            application_access: [
              workspace.toUpperCase() as "LIGHTING" | "AUTOMATION",
            ],
          },
        }));
        const projectId = search.get("project_id") || "";
        const project = p.find((item) => item.id === projectId);
        setData((current) => ({
          ...current,
          customerId:
            project?.customer_id ||
            search.get("customer_id") ||
            current.customerId,
          projectId,
          projectName: project?.name || current.projectName,
          address: project?.address || current.address,
          city: project?.city || current.city,
          state: project?.state || current.state,
          buildingId: "",
          buildingName: projectId ? "" : current.buildingName,
        }));
      })
      .catch((e) => setMessage({ kind: "error", text: e.message }));
  }, [workspace]);
  useEffect(() => {
    if (!data.projectId) {
      setBuildings([]);
      return;
    }
    api<ProjectBuilding[]>(`/api/v1/projects/${data.projectId}/buildings`)
      .then(setBuildings)
      .catch((e) => setMessage({ kind: "error", text: e.message }));
  }, [data.projectId]);
  const chooseProject = (projectId: string) => {
    const project = projects.find((p) => p.id === projectId);
    updateData((current) => ({
      ...current,
      projectId,
      buildingId: "",
      projectName: project?.name || "",
      customerId: project?.customer_id || current.customerId,
      address: project?.address || "",
      city: project?.city || "",
      state: project?.state || "",
      buildingName: projectId ? "" : "Tower A",
    }));
  };
  const chooseBuilding = async (buildingId: string) => {
    if (!buildingId) {
      updateData((current) => ({
        ...current,
        buildingId: "",
        buildingName: "",
      }));
      return;
    }
    try {
      const detail = await api<BuildingDetail>(
        `/api/v1/projects/${data.projectId}/buildings/${buildingId}`,
      );
      updateData((current) => ({
        ...current,
        buildingId,
        buildingName: detail.building.name,
        floors: detail.floors.map((f) => ({
          id: f.id,
          key: key(),
          name: f.name,
          rooms: f.rooms.map((r) => ({
            id: r.id,
            key: key(),
            name: r.name,
            room_type: r.room_type || "",
            area: r.area || undefined,
            occupancy: r.occupancy || undefined,
            notes: r.notes || "",
            requirements: [],
          })),
        })),
      }));
    } catch (e: any) {
      setMessage({ kind: "error", text: e.message });
    }
  };
  useEffect(() => {
    const buildingId = search.get("building_id");
    if (
      buildingId &&
      data.projectId &&
      buildings.some((b) => b.id === buildingId) &&
      data.buildingId !== buildingId
    )
      chooseBuilding(buildingId);
  }, [buildings]);
  useEffect(() => {
    if (!id) return;
    api<Inquiry>(`/api/v1/inquiries/${id}`)
      .then((x) => {
        if (x.workspace.toLowerCase() !== workspace.toLowerCase())
          throw new Error("This inquiry belongs to another application.");
        const structure =
          x.structure?.find((b) => b.id === x.building_id) || x.structure?.[0];
        setNumber(x.number);
        setStep(Math.max(1, Math.min(5, x.wizard_step || 1)));
        setData({
          customerId: x.customer.id,
          newCustomer: {
            company_name: "",
            contact_person: "",
            phone: "",
            email: "",
            address: "",
            city: "",
            state: "",
          },
          projectId: x.project.id,
          projectName: x.project.name,
          address: x.project.address || "",
          city: x.project.city || "",
          state: x.project.state || "",
          buildingId: structure?.id || "",
          buildingName: structure?.name || "Tower A",
          partnerEnabled: Boolean(x.partner),
          partner: x.partner || {
            business_name: "",
            mobile: "",
            email: "",
            address: "",
          },
          floors: (structure?.floors || []).map((f) => ({
            id: f.id,
            key: key(),
            name: f.name,
            rooms: f.rooms.map((r) => ({
              id: r.id,
              key: key(),
              name: r.name,
              room_type: r.room_type || "",
              area: r.area || undefined,
              occupancy: r.occupancy || undefined,
              notes: r.notes || "",
              requirements: r.requirements.map((q) => ({
                product_id: q.product.id,
                quantity: q.quantity,
                notes: q.notes || "",
              })),
            })),
          })),
          notes: x.notes || "",
          portalAccess: {
            enabled: false,
            contact_name: x.customer.contact_person || "",
            email: x.customer.email || "",
            phone: x.customer.phone || "",
            customer_role: "CUSTOMER",
            application_access: [x.workspace],
            send_invitation: true,
            invitation_message: "",
            building_id: x.building_id || undefined,
            confirm_existing_user: false,
          },
        });
        setDirty(false);
        setLoading(false);
      })
      .catch((e) => {
        setMessage({ kind: "error", text: e.message });
        setLoading(false);
      });
  }, [id, workspace]);
  const errors = useMemo(() => validateWizard(data), [data]);
  const stepValid = () =>
    step === 1
      ? errors.filter((x) => !x.includes("floor") && !x.includes("room"))
          .length === 0
      : step === 2
        ? errors.length === 0
        : step === 3
          ? aggregate(data).length > 0
          : true;
  const payload = (updating = false) => ({
    workspace: workspace.toUpperCase(),
    customer_id: data.customerId === "__new__" ? undefined : data.customerId,
    customer:
      data.customerId === "__new__"
        ? {
            company_name: data.newCustomer.company_name.trim(),
            contact_person: data.newCustomer.contact_person.trim() || undefined,
            phone: data.newCustomer.phone.trim(),
            email: data.newCustomer.email.trim(),
            address: data.newCustomer.address.trim() || undefined,
            city: data.newCustomer.city.trim() || data.city.trim(),
            state: data.newCustomer.state.trim() || data.state.trim(),
          }
        : undefined,
    project_id: data.projectId || undefined,
    building_id: data.buildingId || undefined,
    project_name: data.projectName.trim(),
    address: data.address.trim(),
    city: data.city.trim(),
    state: data.state.trim(),
    partner: data.partnerEnabled
      ? {
          business_name: data.partner.business_name.trim(),
          mobile: data.partner.mobile.trim(),
          email: data.partner.email.trim(),
          address: data.partner.address.trim(),
        }
      : undefined,
    ...(updating ? { remove_partner: !data.partnerEnabled } : {}),
    building_name: data.buildingName.trim(),
    floors_data: data.floors.map((f) => ({
      id: f.id,
      name: f.name.trim(),
      rooms: f.rooms.map((r) => ({
        id: r.id,
        name: r.name.trim(),
        room_type: r.room_type?.trim() || undefined,
        area: r.area,
        occupancy: r.occupancy,
        notes: r.notes?.trim() || undefined,
        requirements: r.requirements.map((requirement) => ({
          ...requirement,
          notes: requirement.notes?.trim() || undefined,
        })),
      })),
    })),
    wizard_step: step,
    notes: data.notes.trim() || undefined,
  });
  const save = async (show = true) => {
    if (errors.length) {
      setMessage({ kind: "error", text: errors[0] });
      return null;
    }
    if (!draftId && (!data.projectId || !data.buildingId)) {
      const creating = [
        !data.projectId ? `new project “${data.projectName}”` : null,
        !data.buildingId ? `new building “${data.buildingName}”` : null,
      ]
        .filter(Boolean)
        .join(" and ");
      if (!window.confirm(`This will create a ${creating}. Continue?`))
        return null;
    }
    setBusy(true);
    try {
      let x: Inquiry;
      if (draftId)
        x = await patch<Inquiry>(`/api/v1/inquiries/${draftId}`, payload(true));
      else {
        x = await post<Inquiry>("/api/v1/inquiries", payload(false));
        setDraftId(x.id);
        setNumber(x.number);
      }
      if (data.portalAccess.enabled && !invitationCreated) {
        const invite = await post<any>(
          `/api/v1/inquiries/${x.id}/customer-invitations`,
          { ...data.portalAccess, building_id: data.buildingId || undefined },
        );
        setInvitationCreated(true);
        if (invite.activation_link)
          await navigator.clipboard?.writeText(invite.activation_link);
        if (invite.warning)
          setMessage({
            kind: "warning",
            text: `${invite.warning}${invite.activation_link ? " Activation link copied to clipboard." : ""}`,
          });
      } else if (show)
        setMessage({ kind: "success", text: `Draft ${x.number} saved.` });
      setDirty(false);
      return x;
    } catch (e: any) {
      setMessage({ kind: "error", text: e.message });
      return null;
    } finally {
      setBusy(false);
    }
  };
  const next = () => {
    if (!stepValid()) {
      setMessage({
        kind: "error",
        text:
          step === 3
            ? "Add at least one product before continuing."
            : errors[0] || "Complete the required fields.",
      });
      return;
    }
    setMessage(undefined);
    setStep((s) => Math.min(5, s + 1));
  };
  const submit = async () => {
    if (errors.length || aggregate(data).length === 0) {
      setMessage({
        kind: "error",
        text: errors[0] || "Add at least one product before submission.",
      });
      return;
    }
    const x = await save(false);
    if (!x) return;
    setBusy(true);
    try {
      await post(`/api/v1/inquiries/${x.id}/submit`);
      nav(`/app/${workspace}/inquiries/${x.id}`);
    } catch (e: any) {
      setMessage({ kind: "error", text: e.message });
    } finally {
      setBusy(false);
    }
  };
  if (loading) return <div className="loading">Loading inquiry...</div>;
  return (
    <div className="inquiry-wizard-page">
      <PageTitle
        title={id ? "Edit Inquiry" : "Create Inquiry"}
        subtitle="Build the project scope, room requirements and bill of quantities"
        badge="Admin"
      />
      <InquiryWizardStepper step={step} onStep={setStep} />
      {message && <Notice kind={message.kind}>{message.text}</Notice>}
      <main className="wizard-stage">
        {step === 1 && (
          <StepProjectClient
            data={data}
            setData={updateData}
            customers={customers}
            projects={projects}
            buildings={buildings}
            onProject={chooseProject}
            onBuilding={chooseBuilding}
            inquiryNumber={number}
          />
        )}{" "}
        {step === 2 && (
          <StepProjectStructure data={data} setData={updateData} />
        )}{" "}
        {step === 3 && (
          <StepRoomProducts
            data={data}
            setData={updateData}
            products={products}
          />
        )}{" "}
        {step === 4 && <StepBOQ data={data} products={products} />}{" "}
        {step === 5 && (
          <StepReview
            data={data}
            customers={customers}
            products={products}
            inquiryNumber={number}
          />
        )}
      </main>
      <div className="sticky-actions">
        <div>
          {step === 1 ? (
            <Button
              variant="secondary"
              onClick={() =>
                (!dirty ||
                  window.confirm("Discard unsaved inquiry changes?")) &&
                nav(-1)
              }
            >
              Cancel
            </Button>
          ) : (
            <Button
              variant="secondary"
              onClick={() => setStep((s) => Math.max(1, s - 1))}
            >
              <ChevronLeft size={16} /> Back
            </Button>
          )}
        </div>
        <div>
          <span className="action-step-label">Step {step} of 5</span>
          <Button
            variant="secondary"
            disabled={busy}
            onClick={() => save(true)}
          >
            <Save size={16} /> {busy ? "Saving..." : "Save Draft"}
          </Button>
          {step < 5 ? (
            <Button onClick={next}>
              Continue <ChevronRight size={16} />
            </Button>
          ) : (
            <Button onClick={submit} disabled={busy}>
              {busy ? "Submitting..." : "Create / Submit Inquiry"}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
