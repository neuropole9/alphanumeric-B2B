from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import re
import hashlib
from PIL import Image, ImageDraw
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.config import settings
from app.security import hash_password
from app import models as m
from app.services import next_number, create_quotation_from_inquiry, convert_quotation_to_order, create_invoice_from_order

ADMIN_PERMS=["*"]
USER_PERMS=["products.view","projects.view_own"]


def seed(db: Session):
    if db.scalar(select(func.count()).select_from(m.User)):
        return
    admin = m.User(name="Chaitu's", email="fixture-admin@example.com", password_hash=hash_password("Admin@12345"), role="ADMIN", workspaces=["LIGHTING","AUTOMATION"], permissions=ADMIN_PERMS)
    user = m.User(name="Chaitu S", email="user@alphanumeric-demo.com", password_hash=hash_password("User@12345"), role="USER", workspaces=["LIGHTING","AUTOMATION"], permissions=USER_PERMS)
    db.add_all([admin,user]); db.flush()
    cats=[]
    for w,names in {"LIGHTING":["Indoor Lighting","Outdoor Lighting","Decorative Lighting","Fans","Industrial Lighting"],"AUTOMATION":["Sensors","Controllers","Gateways","Switches / Relays","Interfaces"]}.items():
        for name in names:
            c=m.Category(workspace=w,name=name); db.add(c); cats.append(c)
    db.flush(); cat={(c.workspace,c.name):c for c in cats}
    products=[
      ("LIGHTING","Indoor Lighting","SKU-LP-24W-001","LED Panel Light 24W",100,10,1250,{"Power":"24W","Voltage":"220-240V AC","Frequency":"50 Hz","Lumens":"2400 lm","Color Temperature":"3000K / 4000K / 6500K","CRI":">80","Power Factor":">0.95","IP Rating":"IP44","Dimensions":"300 x 300 mm","Warranty":"3 Years"}),
      ("LIGHTING","Indoor Lighting","SKU-LP-36W-007","LED Panel Light 36W",24,8,1780,{"Power":"36W","Voltage":"220-240V AC","Frequency":"50 Hz","Lumens":"3600 lm","Color Temperature":"4000K / 6500K","CRI":">80","Power Factor":">0.95","IP Rating":"IP44","Dimensions":"600 x 600 mm","Warranty":"3 Years"}),
      ("LIGHTING","Indoor Lighting","SKU-DL-12W-002","LED Downlight 12W",100,10,850,{"Power":"12W","Voltage":"220-240V AC","Lumens":"1200 lm","Color Temperature":"4000K","IP Rating":"IP44"}),
      ("LIGHTING","Indoor Lighting","SKU-TL-20W-003","Track Light 20W",22,10,1980,{"Power":"20W","Mounting":"Track Mounted","Voltage":"220-240V"}),
      ("LIGHTING","Outdoor Lighting","SKU-SL-100W-004","Street Light 100W",3,10,5200,{"Power":"100W","IP Rating":"IP66","Voltage":"100-277V"}),
      ("LIGHTING","Fans","SKU-FN-SMART-005","Ceiling Fan Smart Series",0,5,4200,{"Power":"28W","Motor":"BLDC","Voltage":"220-240V"}),
      ("LIGHTING","Decorative Lighting","SKU-PL-AET-006","Pendant Light Aether",14,5,2450,{"Power":"9W","Color Temperature":"3000K"}),
      ("AUTOMATION","Sensors","AUT-OS-100","Occupancy Sensor",30,8,1850,{"Operating Voltage":"12-24V DC","Protocol":"DALI / Dry Contact","Detection":"PIR","IP Rating":"IP20"}),
      ("AUTOMATION","Switches / Relays","AUT-SS-200","Smart Switch",40,10,2400,{"Operating Voltage":"230V AC","Protocol":"Zigbee","Channels":"4","Relay Rating":"10A"}),
      ("AUTOMATION","Controllers","AUT-LC-300","Lighting Controller",12,4,12500,{"Operating Voltage":"24V DC","Protocol":"DALI / Modbus","Channels":"8"}),
      ("AUTOMATION","Gateways","AUT-GW-400","IoT Gateway",8,3,18900,{"Operating Voltage":"12V DC","Protocol":"Ethernet / Wi-Fi / Modbus","RS485":"2 ports"}),
      ("AUTOMATION","Interfaces","AUT-DI-500","DALI Interface",15,4,6900,{"Protocol":"DALI","Channels":"2","Operating Voltage":"24V DC"}),
    ]
    pmap={}; fmap={}
    for w,cn,sku,name,stock,reorder,price,specs in products:
        family_name="LED Panel Light" if name.startswith("LED Panel Light") else name
        family=fmap.get((w,family_name))
        if not family:
            slug=re.sub(r"[^a-z0-9]+","-",family_name.lower()).strip("-")
            family=m.ProductFamily(workspace=w,category_id=cat[(w,cn)].id,name=family_name,slug=slug,
                brand="AlphaNumeric",short_description=f"Professional {family_name} for commercial projects.",
                full_description=f"A project-ready {family_name.lower()} engineered for dependable commercial installation and lifecycle support.",
                features=["Project-ready specification","Efficient operation","Documented warranty"],
                applications=["Commercial offices","Hospitality","Institutional projects"],status="ACTIVE")
            db.add(family); db.flush(); fmap[(w,family_name)]=family
        variant_name=name.removeprefix(family_name).strip() or name
        p=m.Product(workspace=w,category_id=cat[(w,cn)].id,family_id=family.id,sku=sku,name=name,
            variant_name=variant_name,description=f"Professional {name} for commercial projects.",
            on_hand=max(stock,200),reorder_level=reorder,price=price,cost=Decimal(str(price))*Decimal("0.68"),
            tax_rate=18,hsn_sac="94054090",specs=specs,images=[],lead_time_days=7,warranty=str(specs.get("Warranty","3 Years")))
        db.add(p); pmap[sku]=p
    db.flush()
    media_root=Path(settings.media_root).expanduser().resolve()
    def product_image(product, filename: str, kind: str, accent: str, primary: bool, order: int):
        key=f"fixtures/products/{filename}.png"; path=(media_root/key).resolve(); path.parent.mkdir(parents=True,exist_ok=True)
        image=Image.new("RGB",(1200,900),"#eef3f8"); draw=ImageDraw.Draw(image)
        draw.rectangle((80,80,1120,820),fill="#ffffff",outline="#c8d4e2",width=8)
        if kind=="panel":
            draw.rounded_rectangle((275,220,925,610),radius=35,fill="#fefefe",outline=accent,width=18)
            draw.rounded_rectangle((335,280,865,550),radius=22,fill="#fffbd8",outline="#dce7ef",width=8)
        else:
            draw.ellipse((330,160,870,700),fill="#fdfefe",outline=accent,width=20)
            draw.ellipse((420,250,780,610),fill="#fff6ba",outline="#dce7ef",width=10)
        draw.text((120,745),f"{product.name} | {product.sku}",fill="#17324d",stroke_width=1)
        image.save(path,"PNG",optimize=True)
        data=path.read_bytes()
        db.add(m.ProductMedia(product_family_id=product.family_id,product_id=product.id,storage_key=key,
            workspace=product.workspace,storage_provider="local",original_filename=f"{filename}.png",stored_filename=f"{filename}.png",
            media_type="image/png",mime_type="image/png",file_size=len(data),checksum_sha256=hashlib.sha256(data).hexdigest(),
            upload_status="READY",alt_text=f"{product.name} sanitized product image",caption="Sanitized release validation product image",
            sort_order=order,is_primary=primary,width=1200,height=900))
    product_image(pmap["SKU-LP-24W-001"],"led-panel-front","panel","#1769e0",False,0)
    product_image(pmap["SKU-LP-24W-001"],"led-panel-primary","panel","#0b8f68",True,1)
    product_image(pmap["SKU-DL-12W-002"],"led-downlight-primary","downlight","#7c4dff",True,0)
    customers=[]
    for i,(company,person,city) in enumerate([
      ("Rohini Constructions","Mr. Suresh Kumar","Hyderabad"),("Skyline Infra Pvt Ltd","Ms. Ananya Rao","Bengaluru"),("Greenfield Developers","Mr. Vivek Shah","Chennai"),("Metro Buildtech","Ms. Kavya Nair","Pune"),("Luminous Spaces","Mr. Arjun Mehta","Mumbai")]):
        c=m.Customer(company_name=company,contact_person=person,email=f"contact{i+1}@example.com",phone=f"+91 98{i+1:02d}00 00000",gstin=f"29AACCR1234K1Z{i+1}",address=f"Business District, {city}",city=city,state="Telangana" if city=="Hyderabad" else "Karnataka",status="ACTIVE")
        db.add(c); customers.append(c)
    db.flush()
    project=m.Project(customer_id=customers[0].id,owner_id=admin.id,name="Skyline Towers - Tower A",address="Outer Ring Road",city="Hyderabad",state="Telangana",expected_completion=date.today()+timedelta(days=120),workspace_scope=["LIGHTING","AUTOMATION"])
    db.add(project); db.flush()
    b=m.Building(project_id=project.id,name="Tower A",planned_floors=3); db.add(b); db.flush()
    rooms=[]
    for fi,fname in enumerate(["Ground Floor","First Floor","Second Floor"]):
        f=m.Floor(building_id=b.id,name=fname,sort_order=fi); db.add(f); db.flush()
        db.add(m.MainBoard(project_id=project.id,building_id=b.id,floor_id=f.id,name=f"{fname} Main Board",
                           code=f"MB-{fi+1:02d}",board_type="8-Channel Lighting & Automation Board",
                           system="MIXED",quantity=1,notes="Demo main board configuration"))
        for rn,rt in [("Reception","Lobby & Waiting Area"),("Conference Room","Meeting Room"),("Office 101","Workstations"),("Pantry","Break Area")]:
            r=m.Room(floor_id=f.id,name=rn,room_type=rt,area=120,occupancy=10); db.add(r); rooms.append(r)
    db.flush()
    inq_l=m.Inquiry(number=next_number(db,"inquiry","ANIPL"),customer_id=customers[0].id,project_id=project.id,building_id=b.id,workspace="LIGHTING",owner_id=user.id,status="IN_PROCESS")
    inq_a=m.Inquiry(number=next_number(db,"inquiry","ANIPL"),customer_id=customers[0].id,project_id=project.id,building_id=b.id,workspace="AUTOMATION",owner_id=user.id,status="IN_PROCESS")
    db.add_all([inq_l,inq_a]); db.flush()
    db.add(m.ProjectUser(
        project_id=project.id,user_id=user.id,role="PROJECT_USER",status="ACTIVE",
        permissions=["products.view","projects.view_own","requests.create","proposals.decide"],
        created_by=admin.id,
    )); db.flush()
    for r in rooms[:5]:
        for sku,qty in [("SKU-LP-24W-001",12),("SKU-DL-12W-002",6)]:
            db.add(m.RoomRequirement(inquiry_id=inq_l.id,room_id=r.id,product_id=pmap[sku].id,quantity=qty,unit="Nos"))
            db.add(m.RoomProduct(project_id=project.id,building_id=b.id,floor_id=r.floor_id,room_id=r.id,
                                 product_id=pmap[sku].id,quantity=qty,unit="Nos",approval_status="ADDED",
                                 source="INQUIRY",linked_inquiry_id=inq_l.id,created_by=admin.id,updated_by=admin.id))
    db.add(m.RoomRequirement(inquiry_id=inq_l.id,room_id=rooms[0].id,product_id=pmap["SKU-TL-20W-003"].id,quantity=2,unit="Nos",notes="Track-mounted feature lighting"))
    db.add(m.RoomProduct(project_id=project.id,building_id=b.id,floor_id=rooms[0].floor_id,room_id=rooms[0].id,
                         product_id=pmap["SKU-TL-20W-003"].id,quantity=2,unit="Nos",notes="Track-mounted feature lighting",
                         approval_status="ADDED",source="INQUIRY",linked_inquiry_id=inq_l.id,created_by=admin.id,updated_by=admin.id))
    for r in rooms[:8]:
        for sku,qty in [("AUT-SS-200",6),("AUT-OS-100",2)]:
            db.add(m.RoomRequirement(inquiry_id=inq_a.id,room_id=r.id,product_id=pmap[sku].id,quantity=qty,unit="Nos"))
            db.add(m.RoomProduct(project_id=project.id,building_id=b.id,floor_id=r.floor_id,room_id=r.id,
                                 product_id=pmap[sku].id,quantity=qty,unit="Nos",approval_status="ADDED",
                                 source="INQUIRY",linked_inquiry_id=inq_a.id,created_by=admin.id,updated_by=admin.id))
    db.flush()
    q=create_quotation_from_inquiry(db,inq_l,admin.id); q.status="ACCEPTED"
    order=convert_quotation_to_order(db,q,admin.id); order.status="PROCESSING"
    create_invoice_from_order(db,order,admin.id)
    # Additional inquiry records for dashboards/lists
    statuses=["DRAFT","IN_PROCESS","QUOTED","COMPLETED","IN_PROCESS","DRAFT"]
    for i,s in enumerate(statuses):
        c=customers[(i+1)%len(customers)]
        pr=m.Project(customer_id=c.id,name=["Tech Park","Business Hub","Riverside Residences","Lake View Apartments","City Mall","IT SEZ Phase 1"][i],city=c.city,state=c.state,workspace_scope=["LIGHTING"])
        db.add(pr); db.flush()
        db.add(m.Inquiry(number=next_number(db,"inquiry","ANIPL"),customer_id=c.id,project_id=pr.id,workspace="LIGHTING",owner_id=admin.id if i%2 else user.id,status=s,estimated_value=Decimal(480000+i*125000)))
    db.commit()


def bootstrap_admin(db: Session):
    if db.scalar(select(func.count()).select_from(m.User)):
        return
    if settings.bootstrap_admin_email and settings.bootstrap_admin_password:
        db.add(m.User(name=settings.bootstrap_admin_name,email=settings.bootstrap_admin_email.lower(),password_hash=hash_password(settings.bootstrap_admin_password),role="ADMIN",workspaces=["LIGHTING","AUTOMATION"],permissions=["*"]))
        db.commit()
