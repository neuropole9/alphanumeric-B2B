from __future__ import annotations
from datetime import date, datetime, timezone
from decimal import Decimal
import uuid

from sqlalchemy import (
    String, Integer, DateTime, Date, ForeignKey, Numeric, Text, JSON,
    Boolean, Index, UniqueConstraint, CheckConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


def uid() -> str:
    return str(uuid.uuid4())


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(60), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="USER", index=True)
    partner_id: Mapped[str | None] = mapped_column(ForeignKey("partners.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)
    workspaces: Mapped[list] = mapped_column(JSON, default=list)
    permissions: Mapped[list] = mapped_column(JSON, default=list)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    refresh_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    user: Mapped[User] = relationship()


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_name: Mapped[str] = mapped_column(String(180), index=True)
    contact_person: Mapped[str | None] = mapped_column(String(120), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(60), nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class Partner(Base):
    __tablename__ = "partners"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    business_name: Mapped[str] = mapped_column(String(180), index=True)
    mobile: Mapped[str] = mapped_column(String(60))
    email: Mapped[str] = mapped_column(String(255))
    address: Mapped[str] = mapped_column(Text)
    partner_type: Mapped[str] = mapped_column(String(40), default="OTHER", index=True)
    legal_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(40), nullable=True, unique=True)
    billing_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    shipping_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    territory: Mapped[str | None] = mapped_column(String(100), nullable=True)
    zone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)
    credit_terms_days: Mapped[int] = mapped_column(Integer, default=0)
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    sales_owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    partner_id: Mapped[str | None] = mapped_column(ForeignKey("partners.id", ondelete="SET NULL"), nullable=True, index=True)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    expected_completion: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)
    workspace_scope: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    customer: Mapped[Customer] = relationship()
    partner: Mapped[Partner | None] = relationship()
    owner: Mapped[User | None] = relationship(foreign_keys=[owner_id])


class ProjectUser(Base):
    __tablename__ = "project_users"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_users_project_user"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    building_id: Mapped[str | None] = mapped_column(ForeignKey("buildings.id", ondelete="CASCADE"), nullable=True, index=True)
    role: Mapped[str] = mapped_column(String(32), default="PROJECT_USER")
    permissions: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    project: Mapped[Project] = relationship(foreign_keys=[project_id])
    user: Mapped[User] = relationship(foreign_keys=[user_id])


class Building(Base):
    __tablename__ = "buildings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    building_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)
    planned_floors: Mapped[int] = mapped_column(Integer, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    project: Mapped[Project] = relationship()


class Floor(Base):
    __tablename__ = "floors"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    building_id: Mapped[str] = mapped_column(ForeignKey("buildings.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    building: Mapped[Building] = relationship()


class Room(Base):
    __tablename__ = "rooms"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    floor_id: Mapped[str] = mapped_column(ForeignKey("floors.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    room_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    area: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    occupancy: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    floor: Mapped[Floor] = relationship()


class MainBoard(Base):
    __tablename__ = "main_boards"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_main_boards_quantity_positive"),
        Index("ix_main_boards_scope", "project_id", "building_id", "floor_id", "room_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    building_id: Mapped[str] = mapped_column(ForeignKey("buildings.id", ondelete="CASCADE"), index=True)
    floor_id: Mapped[str] = mapped_column(ForeignKey("floors.id", ondelete="CASCADE"), index=True)
    room_id: Mapped[str | None] = mapped_column(ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(140))
    code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    board_type: Mapped[str] = mapped_column(String(100))
    system: Mapped[str] = mapped_column(String(32), default="MIXED", index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    project: Mapped[Project] = relationship()
    building: Mapped[Building] = relationship()
    floor: Mapped[Floor] = relationship()
    room: Mapped[Room | None] = relationship()


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint("workspace IN ('LIGHTING','AUTOMATION')", name="ck_categories_application"),
        UniqueConstraint("workspace", "parent_id", "name", name="uq_category_application_parent_name"),
        Index("ix_categories_application_parent", "workspace", "parent_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str | None] = mapped_column(String(160), nullable=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    short_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    full_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image_alt_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    catalogue_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    customer_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    search_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    page_title: Mapped[str | None] = mapped_column(String(180), nullable=True)
    meta_description: Mapped[str | None] = mapped_column(String(320), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    parent: Mapped["Category | None"] = relationship(remote_side="Category.id", foreign_keys=[parent_id])


class ProductFamily(Base):
    __tablename__ = "product_families"
    __table_args__ = (
        UniqueConstraint("workspace", "slug", name="uq_product_families_workspace_slug"),
        Index("ix_product_families_workspace_status", "workspace", "status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace: Mapped[str] = mapped_column(String(32), index=True)
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"), index=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    slug: Mapped[str] = mapped_column(String(200))
    brand: Mapped[str] = mapped_column(String(100), default="AlphaNumeric", index=True)
    short_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    full_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    features: Mapped[list] = mapped_column(JSON, default=list)
    applications: Mapped[list] = mapped_column(JSON, default=list)
    suitability_guidance: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    category: Mapped[Category] = relationship()
    variants: Mapped[list["Product"]] = relationship(back_populates="family", foreign_keys="Product.family_id")
    media: Mapped[list["ProductMedia"]] = relationship(back_populates="family", foreign_keys="ProductMedia.product_family_id", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (CheckConstraint("workspace IN ('LIGHTING','AUTOMATION')", name="ck_products_application"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace: Mapped[str] = mapped_column(String(32), index=True)
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"), index=True)
    family_id: Mapped[str | None] = mapped_column(ForeignKey("product_families.id", ondelete="SET NULL"), nullable=True, index=True)
    sku: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    internal_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand: Mapped[str] = mapped_column(String(100), default="AlphaNumeric")
    manufacturer: Mapped[str | None] = mapped_column(String(120), nullable=True)
    variant_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    model_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    barcode: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    search_tags: Mapped[list] = mapped_column(JSON, default=list)
    highlights: Mapped[list] = mapped_column(JSON, default=list)
    features: Mapped[list] = mapped_column(JSON, default=list)
    applications: Mapped[list] = mapped_column(JSON, default=list)
    installation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    care_guide: Mapped[str | None] = mapped_column(Text, nullable=True)
    warranty_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")
    on_hand: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    reserved: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    reorder_level: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=10)
    unit: Mapped[str] = mapped_column(String(30), default="Nos")
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    mrp_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    project_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    dealer_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    reseller_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    minimum_order_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=1)
    pricing_status: Mapped[str] = mapped_column(String(32), default="DRAFT", index=True)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=18)
    hsn_sac: Mapped[str | None] = mapped_column(String(32), nullable=True)
    specs: Mapped[dict] = mapped_column(JSON, default=dict)
    images: Mapped[list] = mapped_column(JSON, default=list)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    warranty: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    category: Mapped[Category] = relationship()
    family: Mapped[ProductFamily | None] = relationship(back_populates="variants", foreign_keys=[family_id])
    media: Mapped[list["ProductMedia"]] = relationship(back_populates="product", foreign_keys="ProductMedia.product_id", cascade="all, delete-orphan")

    @property
    def available(self) -> Decimal:
        return Decimal(self.on_hand or 0) - Decimal(self.reserved or 0)


class ProductPriceHistory(Base):
    __tablename__ = "product_price_history"
    __table_args__ = (
        CheckConstraint("price_type IN ('COST','BASE','MRP','PROJECT','DEALER','RESELLER')", name="ck_product_price_history_type"),
        CheckConstraint("amount >= 0", name="ck_product_price_history_amount"),
        Index("ix_product_price_history_product_effective", "product_id", "price_type", "effective_from"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    price_type: Mapped[str] = mapped_column(String(24), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    tax_inclusive: Mapped[bool] = mapped_column(Boolean, default=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="APPROVED", index=True)
    approval_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class ProductMedia(Base):
    __tablename__ = "product_media"
    __table_args__ = (
        Index("ix_product_media_family_sort", "product_family_id", "sort_order"),
        Index("ix_product_media_variant_sort", "product_id", "sort_order"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    product_family_id: Mapped[str | None] = mapped_column(ForeignKey("product_families.id", ondelete="CASCADE"), nullable=True, index=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=True, index=True)
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    workspace: Mapped[str] = mapped_column(String(32), default="LIGHTING", index=True)
    storage_provider: Mapped[str] = mapped_column(String(32), default="local")
    provider_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    provider_parent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stored_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    upload_status: Mapped[str] = mapped_column(String(32), default="READY", index=True)
    last_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    upload_attempts: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    media_type: Mapped[str] = mapped_column(String(100))
    alt_text: Mapped[str] = mapped_column(String(255))
    caption: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    family: Mapped[ProductFamily | None] = relationship(back_populates="media", foreign_keys=[product_family_id])
    product: Mapped[Product | None] = relationship(back_populates="media", foreign_keys=[product_id])


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    movement_type: Mapped[str] = mapped_column(String(40))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    reference_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    product: Mapped[Product] = relationship()


class Inquiry(Base):
    __tablename__ = "inquiries"
    __table_args__ = (CheckConstraint("workspace IN ('LIGHTING','AUTOMATION')", name="ck_inquiries_application"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    building_id: Mapped[str | None] = mapped_column(ForeignKey("buildings.id", ondelete="SET NULL"), nullable=True, index=True)
    is_project_wide: Mapped[bool] = mapped_column(Boolean, default=False)
    # An inquiry belongs to exactly one business application. Cross-application
    # requirements are rejected by the service layer and migration checks.
    workspace: Mapped[str] = mapped_column(String(32), index=True)
    workspace_scope: Mapped[list] = mapped_column(JSON, default=list)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", index=True)
    wizard_step: Mapped[int] = mapped_column(Integer, default=1)
    source: Mapped[str] = mapped_column(String(32), default="ADMIN")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    linked_inquiry_id: Mapped[str | None] = mapped_column(ForeignKey("inquiries.id", ondelete="SET NULL"), nullable=True, index=True)
    customer: Mapped[Customer] = relationship()
    project: Mapped[Project] = relationship()
    building: Mapped[Building | None] = relationship()
    owner: Mapped[User] = relationship()


class RoomRequirement(Base):
    __tablename__ = "room_requirements"
    __table_args__ = (UniqueConstraint("inquiry_id", "room_id", "product_id", name="uq_requirement_inquiry_room_product"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    inquiry_id: Mapped[str] = mapped_column(ForeignKey("inquiries.id", ondelete="CASCADE"), index=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    unit: Mapped[str] = mapped_column(String(30), default="Nos")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    product: Mapped[Product] = relationship()
    room: Mapped[Room] = relationship()


class RoomProduct(Base):
    __tablename__ = "room_products"
    __table_args__ = (
        UniqueConstraint("room_id", "product_id", name="uq_room_products_room_variant"),
        CheckConstraint("quantity > 0", name="ck_room_products_quantity_positive"),
        Index("ix_room_products_scope", "project_id", "building_id", "floor_id", "room_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    building_id: Mapped[str] = mapped_column(ForeignKey("buildings.id", ondelete="CASCADE"), index=True)
    floor_id: Mapped[str] = mapped_column(ForeignKey("floors.id", ondelete="CASCADE"), index=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    unit: Mapped[str] = mapped_column(String(30), default="Nos")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_status: Mapped[str] = mapped_column(String(32), default="ADDED", index=True)
    source: Mapped[str] = mapped_column(String(40), default="ADMIN_SELECTION", index=True)
    linked_inquiry_id: Mapped[str | None] = mapped_column(ForeignKey("inquiries.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    product: Mapped[Product] = relationship()
    room: Mapped[Room] = relationship()


class ProductProposal(Base):
    __tablename__ = "product_proposals"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_product_proposals_quantity_positive"),
        Index("ix_product_proposals_scope_status", "project_id", "room_id", "status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    building_id: Mapped[str] = mapped_column(ForeignKey("buildings.id", ondelete="CASCADE"), index=True)
    floor_id: Mapped[str] = mapped_column(ForeignKey("floors.id", ondelete="CASCADE"), index=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), index=True)
    product_family_id: Mapped[str | None] = mapped_column(ForeignKey("product_families.id", ondelete="SET NULL"), nullable=True, index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    unit: Mapped[str] = mapped_column(String(30), default="Nos")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", index=True)
    proposed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    proposed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    decided_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_by_id: Mapped[str | None] = mapped_column(ForeignKey("product_proposals.id", ondelete="SET NULL"), nullable=True, index=True)
    linked_inquiry_id: Mapped[str | None] = mapped_column(ForeignKey("inquiries.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    product: Mapped[Product] = relationship()
    family: Mapped[ProductFamily | None] = relationship()


class Quotation(Base):
    __tablename__ = "quotations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    inquiry_id: Mapped[str] = mapped_column(ForeignKey("inquiries.id"), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    building_id: Mapped[str | None] = mapped_column(ForeignKey("buildings.id", ondelete="SET NULL"), nullable=True, index=True)
    workspace: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", index=True)
    quotation_date: Mapped[date] = mapped_column(Date, default=date.today)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_terms: Mapped[str] = mapped_column(String(255), default="30% Advance, 70% Before Dispatch")
    delivery_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    warranty_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    supersedes_id: Mapped[str | None] = mapped_column(ForeignKey("quotations.id", ondelete="SET NULL"), nullable=True, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    grand_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    customer: Mapped[Customer] = relationship()
    project: Mapped[Project] = relationship()
    inquiry: Mapped[Inquiry] = relationship()


class QuotationItem(Base):
    __tablename__ = "quotation_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    quotation_id: Mapped[str] = mapped_column(ForeignKey("quotations.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    description: Mapped[str] = mapped_column(String(255))
    sku: Mapped[str] = mapped_column(String(80))
    qty: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    rate: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    product: Mapped[Product] = relationship()


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    quotation_id: Mapped[str] = mapped_column(ForeignKey("quotations.id"), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    building_id: Mapped[str | None] = mapped_column(ForeignKey("buildings.id", ondelete="SET NULL"), nullable=True, index=True)
    workspace: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="CONFIRMED", index=True)
    order_date: Mapped[date] = mapped_column(Date, default=date.today)
    delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivery_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    dispatch_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    grand_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    customer: Mapped[Customer] = relationship()
    project: Mapped[Project] = relationship()
    quotation: Mapped[Quotation] = relationship()


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    description: Mapped[str] = mapped_column(String(255))
    sku: Mapped[str] = mapped_column(String(80))
    qty: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    rate: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    product: Mapped[Product] = relationship()


class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    building_id: Mapped[str | None] = mapped_column(ForeignKey("buildings.id", ondelete="SET NULL"), nullable=True, index=True)
    workspace: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="ISSUED", index=True)
    invoice_date: Mapped[date] = mapped_column(Date, default=date.today)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    place_of_supply: Mapped[str | None] = mapped_column(String(120), nullable=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    cgst: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    sgst: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    igst: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    round_off: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    grand_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    customer: Mapped[Customer] = relationship()
    project: Mapped[Project | None] = relationship()
    order: Mapped[Order] = relationship()


class InvoiceItem(Base):
    __tablename__ = "invoice_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    description: Mapped[str] = mapped_column(String(255))
    sku: Mapped[str] = mapped_column(String(80))
    hsn_sac: Mapped[str | None] = mapped_column(String(32), nullable=True)
    qty: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    unit: Mapped[str] = mapped_column(String(30), default="Nos")
    rate: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))


class DocumentSequence(Base):
    __tablename__ = "document_sequences"
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    next_value: Mapped[int] = mapped_column(Integer, default=1)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)


class SystemSetting(Base):
    __tablename__ = "system_settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)


class CustomerContact(Base):
    __tablename__ = "customer_contacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(60), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class ProjectStakeholder(Base):
    __tablename__ = "project_stakeholders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    stakeholder_type: Mapped[str] = mapped_column(String(60), index=True)
    organization: Mapped[str | None] = mapped_column(String(180), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(60), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class ProjectDocument(Base):
    __tablename__ = "project_documents"
    __table_args__ = (Index("ix_project_documents_scope", "project_id", "building_id", "floor_id", "room_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    building_id: Mapped[str | None] = mapped_column(ForeignKey("buildings.id", ondelete="CASCADE"), nullable=True, index=True)
    floor_id: Mapped[str | None] = mapped_column(ForeignKey("floors.id", ondelete="CASCADE"), nullable=True, index=True)
    room_id: Mapped[str | None] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(180))
    document_type: Mapped[str] = mapped_column(String(60), index=True)
    revision: Mapped[str] = mapped_column(String(40), default="A")
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    file_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)
    uploaded_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class ProductSpecDefinition(Base):
    __tablename__ = "product_spec_definitions"
    __table_args__ = (
        UniqueConstraint("workspace", "category_id", "product_family_id", "spec_key", name="uq_spec_application_scope_key"),
        Index("ix_spec_definitions_scope_order", "workspace", "category_id", "product_family_id", "sort_order"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"), index=True)
    workspace: Mapped[str] = mapped_column(String(32), default="LIGHTING", index=True)
    product_family_id: Mapped[str | None] = mapped_column(ForeignKey("product_families.id", ondelete="CASCADE"), nullable=True, index=True)
    spec_key: Mapped[str] = mapped_column(String(80))
    label: Mapped[str] = mapped_column(String(120))
    help_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    data_type: Mapped[str] = mapped_column(String(30), default="text")
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    allowed_units: Mapped[list] = mapped_column(JSON, default=list)
    default_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    min_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    max_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    precision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    allowed_values: Mapped[list] = mapped_column(JSON, default=list)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    show_in_catalogue: Mapped[bool] = mapped_column(Boolean, default=True)
    show_in_project_book: Mapped[bool] = mapped_column(Boolean, default=True)
    show_in_quotation_pdf: Mapped[bool] = mapped_column(Boolean, default=False)
    show_in_customer_portal: Mapped[bool] = mapped_column(Boolean, default=True)
    show_in_room_picker: Mapped[bool] = mapped_column(Boolean, default=True)
    show_in_exports: Mapped[bool] = mapped_column(Boolean, default=True)
    searchable: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)


class ProductSpecValue(Base):
    __tablename__ = "product_spec_values"
    __table_args__ = (UniqueConstraint("product_id", "definition_id", name="uq_product_spec_value"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    definition_id: Mapped[str] = mapped_column(ForeignKey("product_spec_definitions.id", ondelete="CASCADE"), index=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class CustomerInvitation(Base):
    __tablename__ = "customer_invitations"
    __table_args__ = (Index("ix_customer_invitations_email_status", "normalized_email", "status"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    inquiry_id: Mapped[str] = mapped_column(ForeignKey("inquiries.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    building_id: Mapped[str | None] = mapped_column(ForeignKey("buildings.id", ondelete="CASCADE"), nullable=True, index=True)
    normalized_email: Mapped[str] = mapped_column(String(255), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    workspace_scope: Mapped[list] = mapped_column(JSON, default=list)
    role: Mapped[str] = mapped_column(String(32), default="USER")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InvitationActivationAttempt(Base):
    __tablename__ = "invitation_activation_attempts"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class MigrationIssue(Base):
    __tablename__ = "migration_issues"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    migration_revision: Mapped[str] = mapped_column(String(32), index=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    issue_code: Mapped[str] = mapped_column(String(80), index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class InvoicePayment(Base):
    __tablename__ = "invoice_payments"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_invoice_payments_amount_positive"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    method: Mapped[str] = mapped_column(String(60))
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    recorded_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ReportSnapshot(Base):
    __tablename__ = "report_snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    building_id: Mapped[str | None] = mapped_column(ForeignKey("buildings.id", ondelete="SET NULL"), nullable=True, index=True)
    report_type: Mapped[str] = mapped_column(String(60), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    generated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class InquiryStageHistory(Base):
    __tablename__ = "inquiry_stage_history"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    inquiry_id: Mapped[str] = mapped_column(ForeignKey("inquiries.id", ondelete="CASCADE"), index=True)
    from_stage: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_stage: Mapped[str] = mapped_column(String(40), index=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    rule_code: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    decided_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Warehouse(Base):
    __tablename__ = "warehouses"
    __table_args__ = (UniqueConstraint("partner_id", "code", name="uq_warehouses_partner_code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    partner_id: Mapped[str | None] = mapped_column(ForeignKey("partners.id", ondelete="CASCADE"), nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(140))
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)
    allow_negative: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class StockLedger(Base):
    __tablename__ = "stock_ledger"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_stock_ledger_quantity_positive"),
        UniqueConstraint("idempotency_key", name="uq_stock_ledger_idempotency"),
        Index("ix_stock_ledger_product_warehouse", "product_id", "warehouse_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True)
    warehouse_id: Mapped[str] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True)
    movement_type: Mapped[str] = mapped_column(String(40), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    direction: Mapped[str] = mapped_column(String(3))
    reference_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)


class Dispatch(Base):
    __tablename__ = "dispatches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"), index=True)
    warehouse_id: Mapped[str | None] = mapped_column(ForeignKey("warehouses.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", index=True)
    delivery_address: Mapped[str] = mapped_column(Text)
    transporter: Mapped[str | None] = mapped_column(String(140), nullable=True)
    vehicle_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    tracking_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    expected_delivery: Mapped[date | None] = mapped_column(Date, nullable=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    receiver_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    proof_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    order: Mapped[Order] = relationship()


class DispatchItem(Base):
    __tablename__ = "dispatch_items"
    __table_args__ = (
        UniqueConstraint("dispatch_id", "order_item_id", name="uq_dispatch_item_order_line"),
        CheckConstraint("quantity > 0", name="ck_dispatch_items_quantity_positive"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    dispatch_id: Mapped[str] = mapped_column(ForeignKey("dispatches.id", ondelete="CASCADE"), index=True)
    order_item_id: Mapped[str] = mapped_column(ForeignKey("order_items.id", ondelete="RESTRICT"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2))


class SerialUnit(Base):
    __tablename__ = "serial_units"
    serial_number: Mapped[str] = mapped_column(String(120), primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True)
    batch_number: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    warehouse_id: Mapped[str | None] = mapped_column(ForeignKey("warehouses.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="IN_STOCK", index=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    room_id: Mapped[str | None] = mapped_column(ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True)
    dispatch_id: Mapped[str | None] = mapped_column(ForeignKey("dispatches.id", ondelete="SET NULL"), nullable=True)
    warranty_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    warranty_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class RMARequest(Base):
    __tablename__ = "rma_requests"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_rma_quantity_positive"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    invoice_id: Mapped[str | None] = mapped_column(ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True)
    serial_number: Mapped[str | None] = mapped_column(ForeignKey("serial_units.serial_number", ondelete="SET NULL"), nullable=True, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    reason: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="REQUESTED", index=True)
    resolution: Mapped[str | None] = mapped_column(String(40), nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    warranty_eligible: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    warranty_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    inspection_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    diagnosis: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    labour_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pickup_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    return_dispatch_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class RMAHistory(Base):
    __tablename__ = "rma_history"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    rma_id: Mapped[str] = mapped_column(ForeignKey("rma_requests.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Announcement(Base):
    __tablename__ = "announcements"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    title: Mapped[str] = mapped_column(String(180))
    content: Mapped[str] = mapped_column(Text)
    audience: Mapped[dict] = mapped_column(JSON, default=dict)
    priority: Mapped[str] = mapped_column(String(20), default="NORMAL", index=True)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", index=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    link_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("user_id", "dedupe_key", name="uq_notification_user_dedupe"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    notification_type: Mapped[str] = mapped_column(String(50), index=True)
    title: Mapped[str] = mapped_column(String(180))
    message: Mapped[str] = mapped_column(Text)
    deep_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(160))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)


class SupportTicket(Base):
    __tablename__ = "support_tickets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(80))
    subject: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(20), default="NORMAL", index=True)
    status: Mapped[str] = mapped_column(String(32), default="OPEN", index=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    assigned_to: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class ResourceAsset(Base):
    __tablename__ = "resource_assets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    title: Mapped[str] = mapped_column(String(180))
    resource_type: Mapped[str] = mapped_column(String(50), index=True)
    workspace: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    audience: Mapped[dict] = mapped_column(JSON, default=dict)
    url: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="PUBLISHED", index=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class FinancialDocument(Base):
    __tablename__ = "financial_documents"
    __table_args__ = (
        UniqueConstraint("document_type", "number", name="uq_financial_document_type_number"),
        Index("ix_financial_document_project_type", "project_id", "document_type"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_type: Mapped[str] = mapped_column(String(32), index=True)
    number: Mapped[str] = mapped_column(String(50), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"), index=True)
    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"), nullable=True, index=True)
    invoice_id: Mapped[str | None] = mapped_column(ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="DRAFT", index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    freight: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    additional_charges: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    grand_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    issued_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class FinancialDocumentItem(Base):
    __tablename__ = "financial_document_items"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_financial_document_item_qty"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("financial_documents.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    description: Mapped[str] = mapped_column(String(500))
    sku: Mapped[str | None] = mapped_column(String(80), nullable=True)
    hsn_sac: Mapped[str | None] = mapped_column(String(32), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    unit: Mapped[str] = mapped_column(String(30), default="Nos")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    line_subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    line_tax: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))


class PricingRule(Base):
    __tablename__ = "pricing_rules"
    __table_args__ = (
        CheckConstraint("priority >= 0", name="ck_pricing_rule_priority"),
        CheckConstraint("min_quantity >= 0", name="ck_pricing_rule_min_qty"),
        Index("ix_pricing_rules_active_dates", "status", "valid_from", "valid_until"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(180))
    scope_type: Mapped[str] = mapped_column(String(32), index=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=True, index=True)
    category_id: Mapped[str | None] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"), nullable=True, index=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=True, index=True)
    partner_id: Mapped[str | None] = mapped_column(ForeignKey("partners.id", ondelete="CASCADE"), nullable=True, index=True)
    zone: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    adjustment_type: Mapped[str] = mapped_column(String(24))
    adjustment_value: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    min_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    max_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    valid_from: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    approval_threshold_percent: Mapped[Decimal | None] = mapped_column(Numeric(7, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="ACTIVE", index=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class SalesTarget(Base):
    __tablename__ = "sales_targets"
    __table_args__ = (CheckConstraint("target_amount >= 0", name="ck_sales_target_amount"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(180))
    target_type: Mapped[str] = mapped_column(String(40), index=True)
    period_type: Mapped[str] = mapped_column(String(20), index=True)
    period_start: Mapped[date] = mapped_column(Date, index=True)
    period_end: Mapped[date] = mapped_column(Date, index=True)
    target_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    sales_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    team: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    zone: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    partner_id: Mapped[str | None] = mapped_column(ForeignKey("partners.id", ondelete="CASCADE"), nullable=True, index=True)
    assigned_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="ACTIVE", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class CatalogueImportJob(Base):
    __tablename__ = "catalogue_import_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace: Mapped[str] = mapped_column(String(32), default="LIGHTING", index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    mode: Mapped[str] = mapped_column(String(20))
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(24), default="PENDING", index=True)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    success_rows: Mapped[int] = mapped_column(Integer, default=0)
    failed_rows: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CatalogueImportRow(Base):
    __tablename__ = "catalogue_import_rows"
    __table_args__ = (UniqueConstraint("job_id", "row_number", name="uq_catalogue_import_job_row"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey("catalogue_import_jobs.id", ondelete="CASCADE"), index=True)
    row_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), index=True)
    sku: Mapped[str | None] = mapped_column(String(80), nullable=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    source_data: Mapped[dict] = mapped_column(JSON, default=dict)
    errors: Mapped[list] = mapped_column(JSON, default=list)


class ExternalCatalogueImport(Base):
    __tablename__ = "external_catalogue_imports"
    __table_args__ = (
        CheckConstraint("workspace = 'LIGHTING'", name="ck_external_catalogue_import_lighting"),
        Index("ix_external_catalogue_import_source", "source_domain", "source_url"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace: Mapped[str] = mapped_column(String(32), default="LIGHTING", index=True)
    source_domain: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str] = mapped_column(String(1000))
    rights_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(32), default="DISCOVERED", index=True)
    discovered_count: Mapped[int] = mapped_column(Integer, default=0)
    imported_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    report: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExternalProductSource(Base):
    __tablename__ = "external_product_sources"
    __table_args__ = (
        UniqueConstraint("workspace", "source_domain", "source_url", name="uq_external_product_source_url"),
        Index("ix_external_product_source_product", "product_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace: Mapped[str] = mapped_column(String(32), default="LIGHTING", index=True)
    source_domain: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str] = mapped_column(String(1000))
    source_model: Mapped[str | None] = mapped_column(String(180), nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    last_import_id: Mapped[str | None] = mapped_column(ForeignKey("external_catalogue_imports.id", ondelete="SET NULL"), nullable=True)
    source_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class CataloguePublication(Base):
    """Immutable catalogue snapshot; published rows never read live product data."""
    __tablename__ = "catalogue_publications"
    __table_args__ = (
        UniqueConstraint("workspace", "code", "version", name="uq_catalogue_publication_version"),
        CheckConstraint("workspace IN ('LIGHTING','AUTOMATION')", name="ck_catalogue_publication_application"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(180))
    code: Mapped[str] = mapped_column(String(80))
    version: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(24), default="DRAFT", index=True)
    cover_title: Mapped[str] = mapped_column(String(180))
    cover_subtitle: Mapped[str | None] = mapped_column(String(300), nullable=True)
    introduction: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_mode: Mapped[str] = mapped_column(String(24), default="NONE")
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RMAEvidence(Base):
    __tablename__ = "rma_evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    rma_id: Mapped[str] = mapped_column(ForeignKey("rma_requests.id", ondelete="CASCADE"), index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    mime_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    uploaded_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class RMAPart(Base):
    __tablename__ = "rma_parts"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_rma_part_qty"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    rma_id: Mapped[str] = mapped_column(ForeignKey("rma_requests.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True)
    warehouse_id: Mapped[str | None] = mapped_column(ForeignKey("warehouses.id", ondelete="SET NULL"), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    added_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class EmailDelivery(Base):
    __tablename__ = "email_deliveries"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_email_delivery_idempotency"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    template_key: Mapped[str] = mapped_column(String(80), index=True)
    recipient: Mapped[str] = mapped_column(String(255), index=True)
    subject: Mapped[str] = mapped_column(String(255))
    text_body: Mapped[str] = mapped_column(Text)
    html_body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="PENDING", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    related_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    related_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (UniqueConstraint("user_id", "event_key", name="uq_notification_preference_event"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    event_key: Mapped[str] = mapped_column(String(80))
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


Index("ix_products_workspace_category", Product.workspace, Product.category_id)
Index("ix_inquiries_workspace_status", Inquiry.workspace, Inquiry.status)
Index("ix_orders_workspace_status", Order.workspace, Order.status)
Index("ix_project_users_user_status", ProjectUser.user_id, ProjectUser.status)
