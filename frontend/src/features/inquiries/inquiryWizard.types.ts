import type { Customer, Partner, Product } from "../../types";

export type WizardRequirement = {
  product_id: string;
  quantity: number;
  notes?: string;
};
export type WizardRoom = {
  id?: string;
  key: string;
  name: string;
  room_type?: string;
  area?: number;
  occupancy?: number;
  notes?: string;
  requirements: WizardRequirement[];
};
export type WizardFloor = {
  id?: string;
  key: string;
  name: string;
  rooms: WizardRoom[];
};
export type WizardData = {
  customerId: string;
  newCustomer: {
    company_name: string;
    contact_person: string;
    phone: string;
    email: string;
    address: string;
    city: string;
    state: string;
  };
  projectName: string;
  projectId: string;
  address: string;
  city: string;
  state: string;
  buildingName: string;
  buildingId: string;
  partnerEnabled: boolean;
  partner: Partner;
  floors: WizardFloor[];
  notes: string;
  portalAccess: {
    enabled: boolean;
    contact_name: string;
    email: string;
    phone: string;
    customer_role: "CUSTOMER" | "PROJECT_USER";
    application_access: ("LIGHTING" | "AUTOMATION")[];
    send_invitation: boolean;
    invitation_message: string;
    building_id?: string;
    confirm_existing_user: boolean;
  };
};
export type ProductLookup = Record<string, Product>;
export const key = () => Math.random().toString(36).slice(2, 10);
export const newRoom = (name = "Room 1"): WizardRoom => ({
  key: key(),
  name,
  room_type: "",
  requirements: [],
});
export const newFloor = (index: number): WizardFloor => ({
  key: key(),
  name: index === 0 ? "Ground Floor" : `Floor ${index}`,
  rooms: [newRoom("Room 1")],
});
export const emptyWizard = (): WizardData => ({
  customerId: "",
  newCustomer: {
    company_name: "",
    contact_person: "",
    phone: "",
    email: "",
    address: "",
    city: "",
    state: "",
  },
  projectName: "",
  projectId: "",
  address: "",
  city: "",
  state: "",
  buildingName: "Tower A",
  buildingId: "",
  partnerEnabled: false,
  partner: { business_name: "", mobile: "", email: "", address: "" },
  floors: [newFloor(0)],
  notes: "",
  portalAccess: {
    enabled: false,
    contact_name: "",
    email: "",
    phone: "",
    customer_role: "CUSTOMER",
    application_access: ["LIGHTING"],
    send_invitation: true,
    invitation_message: "",
    confirm_existing_user: false,
  },
});
export const validEmail = (value: string) =>
  /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
export const validateWizard = (data: WizardData) => {
  const errors: string[] = [];
  if (!data.projectName.trim()) errors.push("Project Name is required.");
  if (!data.address.trim()) errors.push("Site Location is required.");
  if (!data.customerId) errors.push("Select a client.");
  if (!data.buildingId && !data.buildingName.trim())
    errors.push("Enter a building name or select an existing building.");
  if (data.customerId === "__new__") {
    if (!data.newCustomer.company_name.trim())
      errors.push("Client Name is required.");
    if (!data.newCustomer.phone.trim())
      errors.push("Client Phone is required.");
    if (!data.newCustomer.email.trim())
      errors.push("Client Email is required.");
    else if (!validEmail(data.newCustomer.email))
      errors.push("Enter a valid client email address.");
  }
  if (data.partnerEnabled) {
    if (!data.partner.business_name.trim())
      errors.push("Partner Business Name is required.");
    if (data.partner.mobile.trim().length < 5)
      errors.push("Enter a valid partner mobile number.");
    if (!validEmail(data.partner.email))
      errors.push("Enter a valid partner email address.");
    if (!data.partner.address.trim())
      errors.push("Partner Address is required.");
  }
  if (data.portalAccess.enabled) {
    if (!data.portalAccess.contact_name.trim())
      errors.push("Customer portal contact name is required.");
    if (!validEmail(data.portalAccess.email))
      errors.push("Enter a valid customer portal email address.");
    if (!data.portalAccess.application_access.length)
      errors.push("Select customer application access.");
  }
  if (!data.floors.length) errors.push("At least one floor is required.");
  for (const floor of data.floors) {
    if (!floor.name.trim()) errors.push("Every floor needs a name.");
    if (!floor.rooms.length)
      errors.push(`${floor.name || "A floor"} needs at least one room.`);
    for (const room of floor.rooms) {
      if (!room.name.trim()) errors.push("Every room needs a name.");
      if (
        room.area !== undefined &&
        (!Number.isFinite(room.area) || room.area < 0)
      )
        errors.push(`Area in ${room.name || "room"} must be zero or greater.`);
      if (
        room.occupancy !== undefined &&
        (!Number.isInteger(room.occupancy) || room.occupancy < 0)
      )
        errors.push(
          `Occupancy in ${room.name || "room"} must be a whole number of zero or greater.`,
        );
      for (const requirement of room.requirements) {
        if (!requirement.product_id)
          errors.push(`Select a valid product in ${room.name || "room"}.`);
        if (!Number.isFinite(requirement.quantity) || requirement.quantity <= 0)
          errors.push(
            `Product quantity in ${room.name || "room"} must be greater than zero.`,
          );
      }
    }
  }
  return errors;
};
export type CustomerOption = Customer;
