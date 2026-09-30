import { Building2, Handshake, Hash, MapPin, UserRound } from "lucide-react";
import type { Customer, ProjectBuilding, ProjectSummary } from "../../types";
import type { WizardData } from "./inquiryWizard.types";
import { Card } from "../../components/UI";

export default function StepProjectClient({
  data,
  setData,
  customers,
  projects,
  buildings,
  onProject,
  onBuilding,
  inquiryNumber,
}: {
  data: WizardData;
  setData: (d: WizardData) => void;
  customers: Customer[];
  projects: ProjectSummary[];
  buildings: ProjectBuilding[];
  onProject: (id: string) => void;
  onBuilding: (id: string) => void;
  inquiryNumber?: string;
}) {
  const patch = (x: Partial<WizardData>) => setData({ ...data, ...x });
  const nc = (k: string, v: string) =>
    setData({ ...data, newCustomer: { ...data.newCustomer, [k]: v } });
  const partner = (k: string, v: string) =>
    setData({ ...data, partner: { ...data.partner, [k]: v } });
  const portal = (k: string, v: string | boolean | string[]) =>
    setData({ ...data, portalAccess: { ...data.portalAccess, [k]: v } });

  return (
    <div className="wizard-step-content">
      <Card className="wizard-surface">
        <div className="wizard-surface-head">
          <div>
            <span className="eyebrow">Step 1 of 5</span>
            <h2>Project & Client Information</h2>
            <p>Set up the project, customer and optional partner details.</p>
          </div>
          <div className="document-number">
            <span className="document-number-icon">
              <Hash size={18} />
            </span>
            <span>
              <small>Inquiry Number</small>
              <b>{inquiryNumber || "Generated automatically"}</b>
            </span>
          </div>
        </div>

        <section className="wizard-form-section">
          <div className="form-section-head">
            <span>
              <Building2 size={19} />
            </span>
            <div>
              <h3>Project information</h3>
              <p>Primary identity and physical site details.</p>
            </div>
          </div>
          <div className="form-grid three">
            <label>
              Existing project
              <select
                value={data.projectId}
                onChange={(e) => onProject(e.target.value)}
              >
                <option value="">Create a new project</option>
                {projects
                  .filter(
                    (p) =>
                      !data.customerId || p.customer_id === data.customerId,
                  )
                  .map((p) => (
                    <option value={p.id} key={p.id}>
                      {p.name}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Project Name *
              <input
                disabled={Boolean(data.projectId)}
                placeholder="Example: Alpha Tower"
                value={data.projectName}
                onChange={(e) => patch({ projectName: e.target.value })}
              />
            </label>
            <label>
              Site Location *
              <input
                placeholder="Address / site name"
                value={data.address}
                onChange={(e) => patch({ address: e.target.value })}
              />
            </label>
            {data.projectId && (
              <label>
                Existing building
                <select
                  value={data.buildingId}
                  onChange={(e) => onBuilding(e.target.value)}
                >
                  <option value="">Create a new building</option>
                  {buildings.map((b) => (
                    <option value={b.id} key={b.id}>
                      {b.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label>
              Building / Tower
              <input
                disabled={Boolean(data.buildingId)}
                placeholder="Example: Tower A"
                value={data.buildingName}
                onChange={(e) => patch({ buildingName: e.target.value })}
              />
            </label>
            <label>
              <MapPin size={14} /> City
              <input
                placeholder="City"
                value={data.city}
                onChange={(e) => patch({ city: e.target.value })}
              />
            </label>
            <label>
              State
              <input
                placeholder="State"
                value={data.state}
                onChange={(e) => patch({ state: e.target.value })}
              />
            </label>
          </div>
        </section>

        <section className="wizard-form-section">
          <div className="form-section-head">
            <span>
              <UserRound size={19} />
            </span>
            <div>
              <h3>Client information</h3>
              <p>
                Select an existing customer or create a new customer record.
              </p>
            </div>
          </div>
          <div className="form-grid three">
            <label>
              Client *
              <select
                value={data.customerId}
                onChange={(e) =>
                  patch({
                    customerId: e.target.value,
                    projectId: "",
                    buildingId: "",
                  })
                }
              >
                <option value="">Select customer</option>
                {customers.map((c) => (
                  <option value={c.id} key={c.id}>
                    {c.company_name}
                  </option>
                ))}
                <option value="__new__">+ New Customer</option>
              </select>
            </label>
            {data.customerId === "__new__" && (
              <>
                <label>
                  Client Name *
                  <input
                    placeholder="Company / client name"
                    value={data.newCustomer.company_name}
                    onChange={(e) => nc("company_name", e.target.value)}
                  />
                </label>
                <label>
                  Contact Person
                  <input
                    placeholder="Primary contact"
                    value={data.newCustomer.contact_person}
                    onChange={(e) => nc("contact_person", e.target.value)}
                  />
                </label>
                <label>
                  Phone Number *
                  <input
                    placeholder="+91"
                    value={data.newCustomer.phone}
                    onChange={(e) => nc("phone", e.target.value)}
                  />
                </label>
                <label>
                  Email *
                  <input
                    type="email"
                    placeholder="name@company.com"
                    value={data.newCustomer.email}
                    onChange={(e) => nc("email", e.target.value)}
                  />
                </label>
                <label>
                  Address
                  <input
                    placeholder="Billing / office address"
                    value={data.newCustomer.address}
                    onChange={(e) => nc("address", e.target.value)}
                  />
                </label>
              </>
            )}
          </div>
        </section>

        <section className="wizard-form-section">
          <div className="form-section-head">
            <span>
              <UserRound size={19} />
            </span>
            <div>
              <h3>Customer Portal Access</h3>
              <p>
                Invite the customer securely. Passwords are never created or
                displayed by an administrator.
              </p>
            </div>
          </div>
          <label className="check-line">
            <input
              type="checkbox"
              checked={data.portalAccess.enabled}
              onChange={(e) => portal("enabled", e.target.checked)}
            />{" "}
            Create or update customer portal access
          </label>
          {data.portalAccess.enabled && (
            <div className="form-grid three">
              <label>
                Contact name *
                <input
                  value={data.portalAccess.contact_name}
                  onChange={(e) => portal("contact_name", e.target.value)}
                />
              </label>
              <label>
                Email address *
                <input
                  type="email"
                  value={data.portalAccess.email}
                  onChange={(e) => portal("email", e.target.value)}
                />
              </label>
              <label>
                Phone number
                <input
                  value={data.portalAccess.phone}
                  onChange={(e) => portal("phone", e.target.value)}
                />
              </label>
              <label>
                Customer role
                <select
                  value={data.portalAccess.customer_role}
                  onChange={(e) => portal("customer_role", e.target.value as "CUSTOMER" | "PROJECT_USER")}
                >
                  <option value="CUSTOMER">Customer</option>
                  <option value="PROJECT_USER">Project User</option>
                </select>
              </label>
              <label>
                Application access
                <select
                  value={data.portalAccess.application_access.join(",")}
                  onChange={(e) =>
                    portal("application_access", e.target.value.split(","))
                  }
                >
                  <option value="LIGHTING">Lighting</option>
                  <option value="AUTOMATION">Automation</option>
                  <option value="LIGHTING,AUTOMATION">
                    Lighting and Automation
                  </option>
                </select>
              </label>
              <label className="check-line">
                <input
                  type="checkbox"
                  checked={data.portalAccess.send_invitation}
                  onChange={(e) => portal("send_invitation", e.target.checked)}
                />{" "}
                Send invitation email
              </label>
              <label className="check-line span-3">
                <input
                  type="checkbox"
                  checked={data.portalAccess.confirm_existing_user}
                  onChange={(e) =>
                    portal("confirm_existing_user", e.target.checked)
                  }
                />{" "}
                If this email already has an account, I confirm it is the
                intended customer and may receive this project access.
              </label>
              <label className="span-3">
                Optional invitation message
                <textarea
                  value={data.portalAccess.invitation_message}
                  onChange={(e) => portal("invitation_message", e.target.value)}
                />
              </label>
            </div>
          )}
        </section>

        <section className="wizard-form-section partner-section">
          <div className="form-section-head">
            <span>
              <Handshake size={19} />
            </span>
            <div>
              <h3>Optional partner</h3>
              <p>
                Link a channel or implementation partner only when applicable.
              </p>
            </div>
          </div>
          <div
            className="choice-row premium-choice"
            role="group"
            aria-label="Partner selection"
          >
            <button
              type="button"
              className={!data.partnerEnabled ? "selected" : ""}
              onClick={() => patch({ partnerEnabled: false })}
            >
              No partner
            </button>
            <button
              type="button"
              className={data.partnerEnabled ? "selected" : ""}
              onClick={() => patch({ partnerEnabled: true })}
            >
              Add partner
            </button>
          </div>
          {data.partnerEnabled && (
            <div className="form-grid two partner-fields-grid">
              <label>
                Business Name *
                <input
                  value={data.partner.business_name}
                  onChange={(e) => partner("business_name", e.target.value)}
                />
              </label>
              <label>
                Mobile Number *
                <input
                  value={data.partner.mobile}
                  onChange={(e) => partner("mobile", e.target.value)}
                />
              </label>
              <label>
                Email *
                <input
                  type="email"
                  value={data.partner.email}
                  onChange={(e) => partner("email", e.target.value)}
                />
              </label>
              <label>
                Address *
                <textarea
                  value={data.partner.address}
                  onChange={(e) => partner("address", e.target.value)}
                />
              </label>
            </div>
          )}
        </section>
      </Card>
    </div>
  );
}
