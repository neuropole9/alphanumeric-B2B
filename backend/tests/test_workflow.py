import binascii
import struct
import zlib
from datetime import date
from decimal import Decimal
from io import BytesIO
from pypdf import PdfReader

# Test environment and database lifecycle are owned by tests/conftest.py.
# A second database unlink in this module could run after another collected test
# had opened SQLite, leaving the suite connected to a deleted, read-only inode.

from fastapi.testclient import TestClient
from app.main import app
from app.db import Base, engine, SessionLocal
from tests.seed_fixture import seed

Base.metadata.create_all(bind=engine)
with SessionLocal() as _db:
    seed(_db)


def csrf(client: TestClient):
    return {'X-CSRF-Token': client.cookies.get('csrf_token')}


def solid_png(rgb: tuple[int, int, int], width: int = 64, height: int = 64) -> bytes:
    """Create a real, printable RGB PNG without adding an image-library test dependency."""
    signature = b'\x89PNG\r\n\x1a\n'

    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = binascii.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', checksum)

    scanlines = b''.join(b'\x00' + bytes(rgb) * width for _ in range(height))
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    return signature + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(scanlines, 9)) + chunk(b'IEND', b'')


def pdf_rgb_image_colors(pdf_bytes: bytes) -> list[tuple[int, int, int]]:
    """Read first-pixel RGB values from embedded PDF image XObjects."""
    colors: list[tuple[int, int, int]] = []
    for page in PdfReader(BytesIO(pdf_bytes)).pages:
        resources = page.get('/Resources')
        xobjects = resources.get('/XObject') if resources else None
        if not xobjects:
            continue
        for ref in xobjects.values():
            image = ref.get_object()
            if image.get('/Subtype') != '/Image':
                continue
            if str(image.get('/ColorSpace')) != '/DeviceRGB' or image.get('/BitsPerComponent') != 8:
                continue
            data = image.get_data()
            if len(data) >= 3:
                colors.append(tuple(data[:3]))
    return colors


def test_end_to_end_business_flow():
    with TestClient(app) as c:
        r=c.post('/api/v1/auth/login',json={'email':'fixture-admin@example.com','password':'Admin@12345'})
        assert r.status_code==200
        me=c.get('/api/v1/auth/me'); assert me.status_code==200 and me.json()['user']['role']=='ADMIN'
        products=c.get('/api/v1/products?workspace=LIGHTING').json(); assert len(products)>=5
        customers=c.get('/api/v1/customers').json(); assert customers
        create=c.post('/api/v1/inquiries',headers=csrf(c),json={
            'workspace':'LIGHTING','customer_id':customers[0]['id'],'project_name':'Test Tower','building_name':'Tower A','floors':2,
            'room_names':['Reception','Meeting Room'],'requirements':[{'product_id':products[0]['id'],'quantity':4,'apply_all_rooms':True}]
        })
        assert create.status_code==200, create.text
        inquiry=create.json(); detail=c.get(f"/api/v1/inquiries/{inquiry['id']}").json(); assert detail['boq'][0]['quantity']==16
        qr=c.post(f"/api/v1/inquiries/{inquiry['id']}/quotation",headers=csrf(c)); assert qr.status_code==200
        quote=qr.json(); assert quote['grand_total']>0
        assert c.post(f"/api/v1/quotations/{quote['id']}/status",headers=csrf(c),json={'status':'SENT'}).status_code==200
        assert c.post(f"/api/v1/quotations/{quote['id']}/status",headers=csrf(c),json={'status':'ACCEPTED'}).status_code==200
        order=c.post(f"/api/v1/quotations/{quote['id']}/order",headers=csrf(c)); assert order.status_code==200, order.text
        o=order.json(); assert o['status']=='CONFIRMED'
        inv=c.post(f"/api/v1/orders/{o['id']}/invoice",headers=csrf(c)); assert inv.status_code==200
        assert inv.json()['grand_total']==o['grand_total']
        assert c.get(f"/api/v1/invoices/{inv.json()['id']}/pdf").headers['content-type']=='application/pdf'


def test_operational_partner_stock_and_scope_guards():
    with TestClient(app) as c:
        assert c.post('/api/v1/auth/login',json={'email':'fixture-admin@example.com','password':'Admin@12345'}).status_code==200
        partner_body={'business_name':'Secure Distribution Co','partner_type':'DISTRIBUTOR','mobile':'+91 9000000099',
                      'email':'ops-partner@example.com','address':'Hyderabad','credit_terms_days':30,'credit_limit':'250000'}
        created=c.post('/api/v1/partners',headers=csrf(c),json=partner_body)
        assert created.status_code==200,created.text
        assert c.post('/api/v1/partners',headers=csrf(c),json=partner_body).status_code==409
        assert c.post(f"/api/v1/partners/{created.json()['id']}/status",headers=csrf(c),json={'status':'ACTIVE'}).status_code==200

        warehouse=c.post('/api/v1/warehouses',headers=csrf(c),json={'code':'HYD-01','name':'Hyderabad Central'})
        assert warehouse.status_code==200,warehouse.text
        product=c.get('/api/v1/products?workspace=LIGHTING').json()[0]
        receipt={'warehouse_id':warehouse.json()['id'],'product_id':product['id'],'movement_type':'RECEIPT',
                 'quantity':'10','direction':'IN','idempotency_key':'test-receipt-001'}
        first=c.post('/api/v1/stock/movements',headers=csrf(c),json=receipt)
        assert first.status_code==200 and first.json()['balance']==10
        duplicate=c.post('/api/v1/stock/movements',headers=csrf(c),json=receipt)
        assert duplicate.status_code==200 and duplicate.json()['duplicate'] is True
        issue={**receipt,'movement_type':'TRANSFER','quantity':'11','direction':'OUT','idempotency_key':'test-issue-001'}
        assert c.post('/api/v1/stock/movements',headers=csrf(c),json=issue).status_code==409


def test_rma_serial_duplicate_and_unsafe_resource_url_denied():
    with TestClient(app) as c:
        assert c.post('/api/v1/auth/login',json={'email':'fixture-admin@example.com','password':'Admin@12345'}).status_code==200
        assert c.post('/api/v1/resources',headers=csrf(c),json={
            'title':'Unsafe','resource_type':'MANUAL','url':'javascript:alert(1)','audience':{'all':True}
        }).status_code==422
        ticket=c.post('/api/v1/tickets',headers=csrf(c),json={
            'category':'TECHNICAL','subject':'Commissioning support','description':'Need assistance at the project site','priority':'HIGH'
        })
        assert ticket.status_code==200
        assert any(row['id']==ticket.json()['id'] for row in c.get('/api/v1/tickets').json())


def test_release4_pricing_precedence_financial_totals_and_pdf():
    with TestClient(app) as c:
        assert c.post('/api/v1/auth/login',json={'email':'fixture-admin@example.com','password':'Admin@12345'}).status_code==200
        product=c.get('/api/v1/products?workspace=LIGHTING').json()[0]
        today=date.today().isoformat()
        general=c.post('/api/v1/pricing-rules',headers=csrf(c),json={'name':'General 5','scope_type':'GENERAL','adjustment_type':'PERCENT_DISCOUNT','adjustment_value':5,'valid_from':today,'priority':100})
        specific=c.post('/api/v1/pricing-rules',headers=csrf(c),json={'name':'Product 12','scope_type':'PRODUCT','product_id':product['id'],'adjustment_type':'PERCENT_DISCOUNT','adjustment_value':12,'valid_from':today,'priority':100})
        assert general.status_code==200 and specific.status_code==200
        explanation=c.get(f"/api/v1/pricing/explain?product_id={product['id']}&quantity=2")
        assert explanation.status_code==200 and explanation.json()['winning_rule']['name']=='Product 12'
        project=c.get('/api/v1/projects').json()[0]
        detail=c.get(f"/api/v1/projects/{project['id']}").json()
        body={'document_type':'PROFORMA','customer_id':project['customer_id'],'project_id':project['id'],
              'items':[{'product_id':product['id'],'sku':product['sku'],'description':'Authoritative line','quantity':2,'unit_price':100,'tax_rate':18}],
              'discount_percent':10,'freight':5,'additional_charges':0,'subtotal':999999,'grand_total':1}
        created=c.post('/api/v1/financial-documents',headers=csrf(c),json=body)
        assert created.status_code==200,created.text
        assert created.json()['grand_total']==217.4
        assert c.post(f"/api/v1/financial-documents/{created.json()['id']}/issue",headers=csrf(c)).status_code==200
        pdf=c.get(f"/api/v1/financial-documents/{created.json()['id']}/pdf")
        assert pdf.status_code==200 and pdf.content.startswith(b'%PDF')


def test_release4_catalogue_dry_run_atomic_errors_and_formula_safety():
    with TestClient(app) as c:
        assert c.post('/api/v1/auth/login',json={'email':'fixture-admin@example.com','password':'Admin@12345'}).status_code==200
        csv_data=('workspace,category,sku,name,price,tax_rate,specs_json\n'
                  'LIGHTING,Indoor Lighting,SAFE-IMPORT-1,=2+2,1200,18,"{}"\n'
                  'LIGHTING,Missing Category,SAFE-IMPORT-2,Invalid,abc,18,"{}"\n').encode()
        result=c.post('/api/v1/catalogue-imports?dry_run=true&mode=ATOMIC&application=LIGHTING',headers=csrf(c),files={'file':('products.csv',csv_data,'text/csv')})
        assert result.status_code==200,result.text
        assert result.json()['failed_rows']==1 and result.json()['status']=='VALIDATED'
        assert not any(x['sku']=='SAFE-IMPORT-1' for x in c.get('/api/v1/products?workspace=LIGHTING').json())
        errors=c.get(f"/api/v1/catalogue-imports/{result.json()['id']}/errors.csv")
        assert errors.status_code==200 and b'category does not exist' in errors.content


def test_release4_commercial_routes_reject_ordinary_user():
    with TestClient(app) as c:
        assert c.post('/api/v1/auth/login',json={'email':'user@alphanumeric-demo.com','password':'User@12345'}).status_code==200
        assert c.get('/api/v1/pricing-rules').status_code==403
        assert c.get('/api/v1/email-deliveries').status_code==403
        assert c.get('/api/v1/catalogue-imports?application=LIGHTING').status_code==403


def test_user_cannot_manage_users():
    with TestClient(app) as c:
        assert c.post('/api/v1/auth/login',json={'email':'user@alphanumeric-demo.com','password':'User@12345'}).status_code==200
        assert c.get('/api/v1/users').status_code==403


def test_wizard_rejects_mixed_products_and_preserves_anipl_sequence():
    with TestClient(app) as c:
        assert c.post('/api/v1/auth/login',json={'email':'fixture-admin@example.com','password':'Admin@12345'}).status_code==200
        customers=c.get('/api/v1/customers').json()
        lighting=c.get('/api/v1/products?workspace=LIGHTING').json()
        automation=c.get('/api/v1/products?workspace=AUTOMATION').json()
        payload={
            'workspace':'LIGHTING',
            'customer_id':customers[0]['id'],
            'project_name':'Wizard Mixed Systems Project',
            'address':'Test Campus',
            'city':'Hyderabad',
            'state':'Telangana',
            'partner':{'business_name':'Channel Partner Pvt Ltd','mobile':'9876543210','email':'partner@example.com','address':'Hyderabad'},
            'building_name':'Main Tower',
            'wizard_step':4,
            'floors_data':[
                {'name':'Ground Floor','rooms':[
                    {'name':'Reception','requirements':[
                        {'product_id':lighting[0]['id'],'quantity':3},
                        {'product_id':automation[0]['id'],'quantity':2},
                        {'product_id':lighting[0]['id'],'quantity':1},
                    ]},
                    {'name':'Conference Room','requirements':[{'product_id':lighting[1]['id'],'quantity':4}]},
                ]},
                {'name':'Floor 1','rooms':[
                    {'name':'Director Cabin','requirements':[{'product_id':automation[1]['id'],'quantity':1}]},
                ]},
            ],
        }
        r=c.post('/api/v1/inquiries',headers=csrf(c),json=payload)
        assert r.status_code==422 and 'Automation product' in r.text
        payload['floors_data'][0]['rooms'][0]['requirements'] = [
            {'product_id':lighting[0]['id'],'quantity':3},
            {'product_id':lighting[0]['id'],'quantity':1},
        ]
        payload['floors_data'][1]['rooms'][0]['requirements'] = [{'product_id':lighting[1]['id'],'quantity':1}]
        r=c.post('/api/v1/inquiries',headers=csrf(c),json=payload)
        assert r.status_code==200, r.text
        draft=r.json()
        assert draft['number'].startswith('ANIPL') and len(draft['number'])==9
        assert draft['status']=='DRAFT'
        assert draft['workspace_scope']==['LIGHTING']
        iid=draft['id']
        detail=c.get(f'/api/v1/inquiries/{iid}').json()
        assert detail['partner']['business_name']=='Channel Partner Pvt Ltd'
        assert [len(f['rooms']) for f in detail['structure'][0]['floors']]==[2,1]
        reception=detail['structure'][0]['floors'][0]['rooms'][0]
        light_req=next(x for x in reception['requirements'] if x['product']['id']==lighting[0]['id'])
        assert light_req['quantity']==4
        assert c.patch(f'/api/v1/inquiries/{iid}',headers=csrf(c),json={'wizard_step':5,'notes':'Ready for final review'}).status_code==200
        submitted=c.post(f'/api/v1/inquiries/{iid}/submit',headers=csrf(c))
        assert submitted.status_code==200 and submitted.json()['status']=='IN_PROCESS'
        q=c.post(f'/api/v1/inquiries/{iid}/quotation',headers=csrf(c))
        assert q.status_code==200
        linked=c.get(f'/api/v1/inquiries/{iid}/quotation')
        assert linked.status_code==200 and linked.json()['id']==q.json()['id']


def test_project_membership_isolation_product_request_and_dashboard_ranges():
    with TestClient(app) as c:
        assert c.post('/api/v1/auth/login',json={'email':'fixture-admin@example.com','password':'Admin@12345'}).status_code==200
        all_projects=c.get('/api/v1/projects').json()
        assert len(all_projects)>1
        all_users=c.get('/api/v1/users').json()
        demo_user=next(x for x in all_users if x['email']=='user@alphanumeric-demo.com')
        assigned_project=next(p for p in all_projects if p['name']=='Skyline Towers - Tower A')
        forbidden_project=next(p for p in all_projects if p['id']!=assigned_project['id'])
        # Existing assignment is idempotently visible and the user must not need inquiry ownership for access.
        memberships=c.get(f"/api/v1/projects/{assigned_project['id']}/users").json()
        assert any(x['user_id']==demo_user['id'] for x in memberships)

        assert c.post('/api/v1/auth/login',json={'email':'user@alphanumeric-demo.com','password':'User@12345'}).status_code==200
        assert c.get(f"/api/v1/projects/{assigned_project['id']}").status_code==200
        assert c.get(f"/api/v1/projects/{forbidden_project['id']}").status_code==403
        assert c.get('/api/v1/customers').json()==[]
        for range_key, expected in [('30d',30),('3m',13),('6m',6)]:
            dash=c.get(f'/api/v1/dashboard?workspace=LIGHTING&range={range_key}')
            assert dash.status_code==200
            body=dash.json(); assert body['range']==range_key and len(body['trend'])==expected

        product=c.get('/api/v1/products?workspace=LIGHTING').json()[0]
        building=c.get(f"/api/v1/projects/{assigned_project['id']}/buildings").json()[0]
        room=c.get(f"/api/v1/projects/{assigned_project['id']}/buildings/{building['id']}").json()['floors'][0]['rooms'][0]
        request=c.post('/api/v1/product-requests',headers=csrf(c),json={
            'project_id':assigned_project['id'],
            'items':[{'product_id':product['id'],'room_id':room['id'],'quantity':2,'notes':'Customer expansion request'}],
            'notes':'Submitted from Shop Products',
        })
        assert request.status_code==200, request.text
        created=request.json()
        assert created['project']['id']==assigned_project['id']
        assert created['source']=='USER_REQUEST'
        assert created['status']=='IN_PROCESS'
        # Customer user cannot use internal commercial mutation endpoints.
        assert c.post(f"/api/v1/inquiries/{created['id']}/quotation",headers=csrf(c)).status_code==403


def test_normalized_catalogue_media_room_approval_and_building_exports():
    with TestClient(app) as c:
        assert c.post('/api/v1/auth/login',json={'email':'fixture-admin@example.com','password':'Admin@12345'}).status_code==200
        catalogue=c.get('/api/v1/product-families?workspace=LIGHTING').json()
        assert catalogue['total']>=5
        panel=next(item for item in catalogue['items'] if item['name']=='LED Panel Light')
        assert panel['variant_count']==2
        detail=c.get(f"/api/v1/product-families/{panel['id']}")
        assert detail.status_code==200
        family=detail.json()
        assert len(family['variants'])==2
        assert family['primary_image_url']
        image=c.get(family['primary_image_url'])
        assert image.status_code==200 and image.headers['content-type'].startswith('image/') and len(image.content)>100

        # Validated media uploads become database-backed variant media.
        variant=next(row for row in family['variants'] if row['sku']=='SKU-LP-36W-007')
        png=solid_png((75, 110, 210))
        upload=c.post(f"/api/v1/product-variants/{variant['id']}/media",headers=csrf(c),
                      files={'file':('panel.png',png,'image/png')},
                      data={'alt_text':'LED panel light test image','is_primary':'true'})
        assert upload.status_code==200, upload.text
        assert c.get(upload.json()['url']).status_code==200
        bad=c.post(f"/api/v1/product-variants/{variant['id']}/media",headers=csrf(c),
                   files={'file':('bad.png',b'not an image','image/png')},
                   data={'alt_text':'Invalid image'})
        assert bad.status_code==422

        project=next(row for row in c.get('/api/v1/projects').json() if row['name']=='Skyline Towers - Tower A')
        buildings=c.get(f"/api/v1/projects/{project['id']}/buildings")
        assert buildings.status_code==200 and len(buildings.json())==1
        building=buildings.json()[0]
        workspace=c.get(f"/api/v1/projects/{project['id']}/buildings/{building['id']}")
        assert workspace.status_code==200, workspace.text
        body=workspace.json()
        assert body['stats']['floors']==3 and body['stats']['main_boards']==3
        room=body['floors'][0]['rooms'][0]

        # Admin sends a proposal; a project user makes the independent decision.
        first=c.post(f"/api/v1/rooms/{room['id']}/product-proposals",headers=csrf(c),json={
            'product_id':variant['id'],'quantity':2,'send_to_customer':True,'notes':'Recommended for room review'
        })
        second=c.post(f"/api/v1/rooms/{room['id']}/product-proposals",headers=csrf(c),json={
            'product_id':variant['id'],'quantity':3,'send_to_customer':True
        })
        assert first.status_code==200 and second.status_code==200
        assert first.json()['status']=='PENDING_CUSTOMER'
        assert c.patch(f"/api/v1/product-proposals/{first.json()['id']}/decision",headers=csrf(c),json={'decision':'APPROVED'}).status_code==403
        assert c.post('/api/v1/auth/login',json={'email':'user@alphanumeric-demo.com','password':'User@12345'}).status_code==200
        for proposal in (first.json(),second.json()):
            decision=c.patch(f"/api/v1/product-proposals/{proposal['id']}/decision",headers=csrf(c),json={'decision':'APPROVED','comment':'Customer approved'})
            assert decision.status_code==200, decision.text
        room_detail=c.get(f"/api/v1/rooms/{room['id']}").json()
        exact=[row for row in room_detail['products'] if row['product']['id']==variant['id']]
        assert len(exact)==1 and exact[0]['quantity']==5

        pdf=c.get(f"/api/v1/projects/{project['id']}/buildings/{building['id']}/book.pdf")
        assert pdf.status_code==200 and pdf.headers['content-type']=='application/pdf' and pdf.content.startswith(b'%PDF') and len(pdf.content)>5000
        project_pdf=c.get(f"/api/v1/projects/{project['id']}/book.pdf")
        assert project_pdf.status_code==200 and project_pdf.content.startswith(b'%PDF')
        xlsx=c.get(f"/api/v1/projects/{project['id']}/buildings/{building['id']}/boq.xlsx")
        assert xlsx.status_code==200 and xlsx.content.startswith(b'PK')
        sheet=c.get(f"/api/v1/projects/{project['id']}/buildings/{building['id']}/rooms/{room['id']}/sheet.pdf")
        assert sheet.status_code==200 and sheet.content.startswith(b'%PDF')


def test_building_and_report_access_is_project_scoped_and_projects_do_not_mix():
    with TestClient(app) as c:
        assert c.post('/api/v1/auth/login',json={'email':'fixture-admin@example.com','password':'Admin@12345'}).status_code==200
        customers=c.get('/api/v1/customers').json()
        customer=customers[0]
        product=c.get('/api/v1/products?workspace=LIGHTING').json()[0]
        created=c.post('/api/v1/inquiries',headers=csrf(c),json={
            'workspace':'LIGHTING','customer_id':customer['id'],'project_name':'Isolated Second Site',
            'address':'Separate address','building_name':'Isolated Tower','floors_data':[
                {'name':'Ground Floor','rooms':[{'name':'Only Room','requirements':[{'product_id':product['id'],'quantity':1}]}]}
            ]
        })
        assert created.status_code==200, created.text
        inquiry=created.json(); isolated_project=inquiry['project']['id']
        isolated_building=c.get(f'/api/v1/projects/{isolated_project}/buildings').json()[0]
        first_project=next(row for row in c.get('/api/v1/projects').json() if row['name']=='Skyline Towers - Tower A')
        first_detail=c.get(f"/api/v1/projects/{first_project['id']}").json()
        assert all(row['id']!=inquiry['id'] for row in first_detail['inquiries'])

        assert c.post('/api/v1/auth/login',json={'email':'user@alphanumeric-demo.com','password':'User@12345'}).status_code==200
        assert c.get(f"/api/v1/projects/{isolated_project}/buildings/{isolated_building['id']}").status_code==403
        assert c.get(f"/api/v1/projects/{isolated_project}/buildings/{isolated_building['id']}/book.pdf").status_code==403
        assert c.get(f"/api/v1/projects/{isolated_project}/buildings/{isolated_building['id']}/boq.xlsx").status_code==403


def test_existing_context_documents_structure_permissions_and_payments():
    with TestClient(app) as c:
        assert c.post('/api/v1/auth/login',json={'email':'fixture-admin@example.com','password':'Admin@12345'}).status_code==200
        project=next(row for row in c.get('/api/v1/projects').json() if row['name']=='Skyline Towers - Tower A')
        before=c.get(f"/api/v1/projects/{project['id']}/buildings").json()
        building=before[0]
        workspace=c.get(f"/api/v1/projects/{project['id']}/buildings/{building['id']}").json()
        floor=workspace['floors'][0]; room=floor['rooms'][0]
        product=c.get('/api/v1/products?workspace=LIGHTING').json()[0]
        inquiry=c.post('/api/v1/inquiries',headers=csrf(c),json={
            'workspace':'LIGHTING','customer_id':project['customer_id'],'project_id':project['id'],
            'building_id':building['id'],'project_name':project['name'],'building_name':building['name'],
            'address':project.get('address') or 'Existing site','floors_data':[{
                'id':floor['id'],'name':floor['name'],'rooms':[{'id':room['id'],'name':room['name'],
                'requirements':[{'product_id':product['id'],'quantity':1}]}]}],
        })
        assert inquiry.status_code==200, inquiry.text
        after=c.get(f"/api/v1/projects/{project['id']}/buildings").json()
        assert len(after)==len(before) and after[0]['floor_count']==before[0]['floor_count'] and after[0]['room_count']==before[0]['room_count']

        png=solid_png((90, 130, 190))
        uploaded=c.post(f"/api/v1/projects/{project['id']}/documents",headers=csrf(c),
            files={'file':('floor-plan.png',png,'image/png')},
            data={'title':'Ground Floor Plan','document_type':'FLOOR_PLAN','revision':'B','building_id':building['id'],'floor_id':floor['id']})
        assert uploaded.status_code==200, uploaded.text
        document=uploaded.json()
        assert c.get(document['preview_url']).content==png
        listed=c.get(f"/api/v1/projects/{project['id']}/documents?building_id={building['id']}").json()
        assert any(row['id']==document['id'] for row in listed)
        book=c.get(f"/api/v1/projects/{project['id']}/buildings/{building['id']}/book.pdf")
        assert book.status_code==200 and book.content.startswith(b'%PDF') and len(book.content)>5000

        created_floor=c.post(f"/api/v1/projects/{project['id']}/buildings/{building['id']}/floors",headers=csrf(c),json={'name':'Test Archive Floor'})
        assert created_floor.status_code==200
        created_room=c.post(f"/api/v1/floors/{created_floor.json()['id']}/rooms",headers=csrf(c),json={'name':'Sample Room','room_type':'Office'})
        assert created_room.status_code==200
        assert c.delete(f"/api/v1/rooms/{created_room.json()['id']}",headers=csrf(c)).json()['status']=='ARCHIVED'
        assert c.delete(f"/api/v1/floors/{created_floor.json()['id']}",headers=csrf(c)).json()['status']=='ARCHIVED'

        users=c.get(f"/api/v1/projects/{project['id']}/users").json(); membership=users[0]
        assert c.patch(f"/api/v1/projects/{project['id']}/users/{membership['user_id']}",headers=csrf(c),json={
            'permissions':['products.view','projects.view_own','requests.create','proposals.decide','commercial.documents.view']
        }).status_code==200
        invoice=c.get('/api/v1/invoices?workspace=LIGHTING').json()[0]
        payment=c.post(f"/api/v1/invoices/{invoice['id']}/payments",headers=csrf(c),json={'amount':1,'method':'BANK_TRANSFER','reference':'TEST-1'})
        assert payment.status_code==200 and payment.json()['paid_total']==1
        assert payment.json()['company']['name']

        assert c.post('/api/v1/auth/login',json={'email':'user@alphanumeric-demo.com','password':'User@12345'}).status_code==200
        user_project=c.get(f"/api/v1/projects/{project['id']}")
        assert user_project.status_code==200 and user_project.json()['quotations']
        assert 'grand_total' not in user_project.json()['quotations'][0]


def test_exact_project_workspace_103_unit_commercial_lifecycle_is_scoped_and_idempotent():
    """Acceptance scenario: persisted physical structure -> BOQ -> quote -> order -> invoice."""
    with TestClient(app) as c:
        assert c.post('/api/v1/auth/login', json={'email':'fixture-admin@example.com','password':'Admin@12345'}).status_code == 200
        customer = c.post('/api/v1/customers', headers=csrf(c), json={
            'company_name':'Chaitanya Acceptance','contact_person':'Chaitanya','phone':'9000000000',
            'email':'chaitanya.acceptance@example.com','address':'Hyderabad','city':'Hyderabad','state':'Telangana'
        })
        assert customer.status_code == 200, customer.text
        products = c.get('/api/v1/products?workspace=LIGHTING').json()[:4]
        assert len(products) == 4
        payload = {
            'workspace':'LIGHTING','customer_id':customer.json()['id'],'project_name':'Arcot Acceptance',
            'address':'East Evenu','city':'Hyderabad','state':'Telangana','building_name':'East Evenu',
            'wizard_step':5,'floors_data':[
                {'name':'Ground Floor','rooms':[
                    {'name':'Reception','requirements':[{'product_id':products[0]['id'],'quantity':20}]},
                    {'name':'Conference','requirements':[{'product_id':products[1]['id'],'quantity':20}]},
                    {'name':'Lobby','requirements':[{'product_id':products[2]['id'],'quantity':20}]},
                ]},
                {'name':'First Floor','rooms':[
                    {'name':'Cabin','requirements':[{'product_id':products[3]['id'],'quantity':20}]},
                    {'name':'Open Office','requirements':[{'product_id':products[0]['id'],'quantity':23}]},
                ]},
            ],
        }
        created = c.post('/api/v1/inquiries', headers=csrf(c), json=payload)
        assert created.status_code == 200, created.text
        inquiry = created.json(); inquiry_id = inquiry['id']; project_id = inquiry['project']['id']
        building_id = c.get(f'/api/v1/projects/{project_id}/buildings').json()[0]['id']
        assert c.post(f'/api/v1/inquiries/{inquiry_id}/submit', headers=csrf(c)).status_code == 200

        project = c.get(f'/api/v1/projects/{project_id}')
        assert project.status_code == 200
        body = project.json()
        assert body['stats']['buildings'] == 1
        assert body['stats']['floors'] == 2
        assert body['stats']['rooms'] == 5
        assert body['stats']['unique_products'] == 4
        assert body['stats']['products'] == 103
        inquiry_detail = c.get(f'/api/v1/inquiries/{inquiry_id}').json()
        assert len(inquiry_detail['boq']) == 4
        assert sum(row['quantity'] for row in inquiry_detail['boq']) == 103
        assert sum(len(row['breakdown']) for row in inquiry_detail['boq']) == 5

        quotation = c.post(f'/api/v1/inquiries/{inquiry_id}/quotation', headers=csrf(c))
        assert quotation.status_code == 200
        quote = quotation.json()
        duplicate_quote = c.post(f'/api/v1/inquiries/{inquiry_id}/quotation', headers=csrf(c))
        assert duplicate_quote.status_code == 200 and duplicate_quote.json()['id'] == quote['id']
        expected_subtotal = sum(Decimal(str(row['quantity'])) * Decimal(str(row['rate'])) for row in inquiry_detail['boq'])
        expected_tax = sum(Decimal(str(row['quantity'])) * Decimal(str(row['rate'])) * Decimal(str(row['tax_rate'])) / 100
                           for row in inquiry_detail['boq'])
        assert Decimal(str(quote['subtotal'])) == expected_subtotal.quantize(Decimal('0.01'))
        assert Decimal(str(quote['tax_total'])) == expected_tax.quantize(Decimal('0.01'))
        assert any(row['id'] == quote['id'] for row in c.get(f'/api/v1/projects/{project_id}/quotations').json())
        assert c.post(f"/api/v1/quotations/{quote['id']}/status", headers=csrf(c), json={'status':'SENT'}).status_code == 200
        assert c.post(f"/api/v1/quotations/{quote['id']}/status", headers=csrf(c), json={'status':'ACCEPTED'}).status_code == 200
        order = c.post(f"/api/v1/quotations/{quote['id']}/order", headers=csrf(c))
        assert order.status_code == 200
        duplicate_order = c.post(f"/api/v1/quotations/{quote['id']}/order", headers=csrf(c))
        assert duplicate_order.status_code == 200 and duplicate_order.json()['id'] == order.json()['id']
        invoice = c.post(f"/api/v1/orders/{order.json()['id']}/invoice", headers=csrf(c))
        assert invoice.status_code == 200
        duplicate_invoice = c.post(f"/api/v1/orders/{order.json()['id']}/invoice", headers=csrf(c))
        assert duplicate_invoice.status_code == 200 and duplicate_invoice.json()['id'] == invoice.json()['id']
        refreshed = c.get(f'/api/v1/projects/{project_id}').json()
        assert {row['id'] for row in refreshed['quotations']} == {quote['id']}
        assert {row['id'] for row in refreshed['orders']} == {order.json()['id']}
        assert {row['id'] for row in refreshed['invoices']} == {invoice.json()['id']}

        quotation_document = c.get(f"/api/v1/quotations/{quote['id']}/pdf?download=true")
        invoice_document = c.get(f"/api/v1/invoices/{invoice.json()['id']}/pdf?download=true")
        assert quotation_document.status_code == 200
        assert invoice_document.status_code == 200
        assert quotation_document.headers['content-type'] == 'application/pdf'
        assert invoice_document.headers['content-type'] == 'application/pdf'
        assert 'attachment; filename="Quotation_' in quotation_document.headers['content-disposition']
        assert 'attachment; filename="Invoice_' in invoice_document.headers['content-disposition']
        quotation_text = '\n'.join(page.extract_text() or '' for page in PdfReader(BytesIO(quotation_document.content)).pages)
        invoice_text = '\n'.join(page.extract_text() or '' for page in PdfReader(BytesIO(invoice_document.content)).pages)
        assert 'QUOTATION' in quotation_text.upper()
        assert 'INVOICE' not in quotation_text.upper()
        assert 'INVOICE' in invoice_text.upper()
        assert quotation_document.content != invoice_document.content
        assert c.get(f"/api/v1/quotations/{invoice.json()['id']}/pdf").status_code == 404
        assert c.get(f"/api/v1/invoices/{quote['id']}/pdf").status_code == 404
        assert c.get('/api/v1/quotations/missing-document/pdf').status_code == 404
        assert c.get('/api/v1/invoices/missing-document/pdf').status_code == 404
        # Invoice generation must never replace or mutate the quotation document.
        quotation_again = c.get(f"/api/v1/quotations/{quote['id']}/pdf?download=true")
        quotation_again_text = '\n'.join(page.extract_text() or '' for page in PdfReader(BytesIO(quotation_again.content)).pages)
        assert quotation_again_text == quotation_text

        project_book = c.get(f'/api/v1/projects/{project_id}/book.pdf?download=true')
        assert project_book.status_code == 200
        assert project_book.headers['content-type'] == 'application/pdf'
        assert 'attachment; filename="AlphaNumeric_Chaitanya-Acceptance_Arcot-Acceptance_Project-Book_' in project_book.headers['content-disposition']
        project_book_reader = PdfReader(BytesIO(project_book.content))
        project_book_text = '\n'.join(page.extract_text() or '' for page in project_book_reader.pages)
        assert len(project_book_reader.pages) >= 2
        assert all(len((page.extract_text() or "").splitlines()) >= 6
                   for page in project_book_reader.pages)
        assert 'PRODUCT TECHNICAL SPECIFICATIONS' in project_book_text.upper()
        for heading in [
            'PROJECT CONFIGURATION BOOK',
            'Inquiry, Customer & Partner Information',
            'Project Overview',
            'Complete Floor View',
            'Room Configuration',
            'Aggregated Bill of Quantities',
            'Commercial History',
        ]:
            assert heading in project_book_text
        assert '103' in project_book_text

        building_book = c.get(f'/api/v1/projects/{project_id}/buildings/{building_id}/book.pdf?download=true')
        assert building_book.status_code == 200
        assert building_book.headers['content-type'] == 'application/pdf'
        assert '_Building-Book_' in building_book.headers['content-disposition']
        assert len(PdfReader(BytesIO(building_book.content)).pages) >= 2

        for endpoint, signature in [
            (f'/api/v1/projects/{project_id}/book.pdf', b'%PDF'),
            (f'/api/v1/projects/{project_id}/boq.xlsx', b'PK'),
            (f'/api/v1/projects/{project_id}/buildings/{building_id}/book.pdf', b'%PDF'),
            (f'/api/v1/projects/{project_id}/buildings/{building_id}/boq.xlsx', b'PK'),
            (f"/api/v1/quotations/{quote['id']}/pdf", b'%PDF'),
            (f"/api/v1/invoices/{invoice.json()['id']}/pdf", b'%PDF'),
        ]:
            report = c.get(endpoint)
            assert report.status_code == 200, (endpoint, report.text[:200])
            assert report.content.startswith(signature)

        structure = inquiry_detail['structure'][0]
        update = {**payload, 'project_id':project_id, 'building_id':building_id,
                  'floors_data':[{'id':floor['id'],'name':floor['name'],'rooms':[
                      {'id':room['id'],'name':room['name'],'room_type':room.get('room_type'),
                       'requirements':[{'product_id':req['product']['id'],'quantity':req['quantity']} for req in room['requirements']]}
                      for room in floor['rooms']]} for floor in structure['floors']]}
        edited = c.patch(f'/api/v1/inquiries/{inquiry_id}', headers=csrf(c), json=update)
        assert edited.status_code == 200, edited.text
        after = c.get(f'/api/v1/projects/{project_id}').json()
        assert (after['stats']['buildings'], after['stats']['floors'], after['stats']['rooms'], after['stats']['products']) == (1,2,5,103)

        other_project = next(row for row in c.get('/api/v1/projects').json() if row['id'] != project_id)
        other_detail = c.get(f"/api/v1/projects/{other_project['id']}").json()
        assert all(row['id'] != inquiry_id for row in other_detail['inquiries'])
        assert all(row['id'] != quote['id'] for row in other_detail['quotations'])
        assert c.post('/api/v1/auth/login', json={'email':'user@alphanumeric-demo.com','password':'User@12345'}).status_code == 200
        assert c.get(f'/api/v1/projects/{project_id}').status_code == 403
        assert c.get(f'/api/v1/projects/{project_id}/book.pdf').status_code == 403
        assert c.get(f"/api/v1/quotations/{quote['id']}/pdf").status_code == 403
        assert c.get(f"/api/v1/invoices/{invoice.json()['id']}/pdf").status_code == 403


def test_exact_variant_primary_image_order_controls_project_book_thumbnail():
    """Three-image regression: Project Book uses exactly the selected variant image."""
    red = (193, 41, 61)
    green = (31, 143, 89)
    blue = (37, 92, 191)

    with TestClient(app) as c:
        assert c.post('/api/v1/auth/login', json={'email':'fixture-admin@example.com','password':'Admin@12345'}).status_code == 200

        family_summary = next(
            item for item in c.get('/api/v1/product-families?workspace=LIGHTING').json()['items']
            if item['name'] == 'LED Panel Light'
        )
        family = c.get(f"/api/v1/product-families/{family_summary['id']}").json()
        template = next(item for item in family['variants'] if item['sku'] == 'SKU-LP-36W-007')
        created = c.post(
            f"/api/v1/product-families/{family['id']}/variants",
            headers=csrf(c),
            json={
                'sku':'TEST-MEDIA-REG-001',
                'name':'LED Panel Media Regression',
                'variant_name':'Media Regression',
                'description':'Three-image PDF selection regression fixture.',
                'unit':'Nos',
                'price':1250,
                'cost':800,
                'tax_rate':18,
                'hsn_sac':template.get('hsn_sac'),
                'on_hand':50,
                'reorder_level':5,
                'specs':template.get('specs') or {},
                'lead_time_days':7,
                'warranty':'3 Years',
            },
        )
        assert created.status_code == 200, created.text
        variant_id = created.json()['id']

        uploaded = []
        for label, rgb, primary in [('A', red, True), ('B', green, False), ('C', blue, False)]:
            result = c.post(
                f'/api/v1/product-variants/{variant_id}/media',
                headers=csrf(c),
                files={'file':(f'image-{label}.png', solid_png(rgb), 'image/png')},
                data={'alt_text':f'Media regression image {label}', 'is_primary':str(primary).lower()},
            )
            assert result.status_code == 200, result.text
            uploaded.append(result.json())

        image_a, image_b, image_c = uploaded
        assert c.patch(f"/api/v1/product-media/{image_b['id']}", headers=csrf(c), json={'is_primary':True}).status_code == 200
        product = c.get(f'/api/v1/products/{variant_id}')
        assert product.status_code == 200
        product_body = product.json()
        assert product_body['primary_image_url'] == image_b['url']
        assert [row['id'] for row in product_body['media']] == [image_b['id'], image_a['id'], image_c['id']]
        assert len({row['id'] for row in product_body['media']}) == 3

        project = next(row for row in c.get('/api/v1/projects').json() if row['name'] == 'Skyline Towers - Tower A')
        building = c.get(f"/api/v1/projects/{project['id']}/buildings").json()[0]
        workspace = c.get(f"/api/v1/projects/{project['id']}/buildings/{building['id']}").json()
        room = workspace['floors'][0]['rooms'][0]
        proposal = c.post(
            f"/api/v1/rooms/{room['id']}/product-proposals",
            headers=csrf(c),
            json={'product_id':variant_id, 'quantity':2, 'send_to_customer':True, 'notes':'Media regression'},
        )
        assert proposal.status_code == 200 and proposal.json()['status'] == 'PENDING_CUSTOMER'

        assert c.post('/api/v1/auth/login', json={'email':'user@alphanumeric-demo.com','password':'User@12345'}).status_code == 200
        decision = c.patch(
            f"/api/v1/product-proposals/{proposal.json()['id']}/decision",
            headers=csrf(c),
            json={'decision':'APPROVED','comment':'Approved for media regression'},
        )
        assert decision.status_code == 200, decision.text
        assert c.post('/api/v1/auth/login', json={'email':'fixture-admin@example.com','password':'Admin@12345'}).status_code == 200

        book_b = c.get(f"/api/v1/projects/{project['id']}/book.pdf")
        assert book_b.status_code == 200
        colors_b = pdf_rgb_image_colors(book_b.content)
        # The selected image appears in both the room-product table and the
        # technical appendix; sibling images must never leak into either.
        assert colors_b.count(green) == 2
        assert red not in colors_b and blue not in colors_b

        assert c.patch(f"/api/v1/product-media/{image_c['id']}", headers=csrf(c), json={'is_primary':True}).status_code == 200
        book_c = c.get(f"/api/v1/projects/{project['id']}/book.pdf")
        colors_c = pdf_rgb_image_colors(book_c.content)
        assert colors_c.count(blue) == 2
        assert red not in colors_c and green not in colors_c

        assert c.patch(f"/api/v1/product-media/{image_c['id']}", headers=csrf(c), json={'is_primary':False}).status_code == 200
        for media, order in [(image_a, 0), (image_b, 1), (image_c, 2)]:
            assert c.patch(f"/api/v1/product-media/{media['id']}", headers=csrf(c), json={'sort_order':order}).status_code == 200
        product_ordered = c.get(f'/api/v1/products/{variant_id}').json()
        assert product_ordered['primary_image_url'] == image_a['url']
        book_a = c.get(f"/api/v1/projects/{project['id']}/book.pdf")
        colors_a = pdf_rgb_image_colors(book_a.content)
        assert colors_a.count(red) == 2
        assert green not in colors_a and blue not in colors_a


def test_database_url_normalization_for_render_postgres_urls():
    from app.db import is_postgresql_url, normalized_database_url
    assert normalized_database_url("postgres://user:pass@host/db") == "postgresql+psycopg://user:pass@host/db"
    assert normalized_database_url("postgresql://user:pass@host/db") == "postgresql+psycopg://user:pass@host/db"
    assert normalized_database_url("postgresql+psycopg://user:pass@host/db") == "postgresql+psycopg://user:pass@host/db"
    assert is_postgresql_url("postgres://user:pass@host/db") is True
    assert is_postgresql_url("postgresql://user:pass@host/db") is True
    assert is_postgresql_url("sqlite:///./alphanumeric.db") is False


def test_created_user_must_change_password_and_can_change_it():
    email = "password-change-regression@example.com"
    initial = "InitialPass@123"
    replacement = "ReplacementPass@456"
    with TestClient(app) as c:
        assert c.post('/api/v1/auth/login', json={'email':'fixture-admin@example.com','password':'Admin@12345'}).status_code == 200
        created = c.post('/api/v1/users', headers=csrf(c), json={
            'name':'Password Change Regression', 'email':email, 'password':initial,
            'role':'USER', 'workspaces':['LIGHTING'], 'permissions':['projects.view_own']
        })
        assert created.status_code == 200, created.text
        assert created.json()['must_change_password'] is True
        assert c.post('/api/v1/auth/logout', headers=csrf(c)).status_code == 200
        login = c.post('/api/v1/auth/login', json={'email':email,'password':initial})
        assert login.status_code == 200
        assert login.json()['user']['must_change_password'] is True
        wrong = c.post('/api/v1/auth/change-password', headers=csrf(c), json={
            'current_password':'wrong-password', 'new_password':replacement
        })
        assert wrong.status_code == 422
        changed = c.post('/api/v1/auth/change-password', headers=csrf(c), json={
            'current_password':initial, 'new_password':replacement
        })
        assert changed.status_code == 200
        me = c.get('/api/v1/auth/me')
        assert me.status_code == 200 and me.json()['user']['must_change_password'] is False
        assert c.post('/api/v1/auth/logout', headers=csrf(c)).status_code == 200
        assert c.post('/api/v1/auth/login', json={'email':email,'password':replacement}).status_code == 200


def test_release5_super_admin_and_application_scoped_users():
    from app.security import hash_password
    with SessionLocal() as db:
        if not db.scalar(__import__('sqlalchemy').select(__import__('app.models', fromlist=['User']).User).where(__import__('app.models', fromlist=['User']).User.email=='super5@example.com')):
            from app import models as m
            db.add_all([
                m.User(name='Release 5 Super',email='super5@example.com',password_hash=hash_password('SuperAdmin@123'),role='SUPER_ADMIN',status='ACTIVE',workspaces=['LIGHTING','AUTOMATION'],permissions=['*']),
                m.User(name='Lighting Only',email='lighting5@example.com',password_hash=hash_password('LightingOnly@123'),role='USER',status='ACTIVE',workspaces=['LIGHTING'],permissions=[]),
            ]); db.commit()
    with TestClient(app) as c:
        assert c.post('/api/v1/auth/login',json={'email':'super5@example.com','password':'SuperAdmin@123'}).status_code==200
        assert c.get('/api/v1/users').status_code==200
        assert c.get('/api/v1/products?workspace=AUTOMATION').status_code==200
        assert c.post('/api/v1/auth/login',json={'email':'lighting5@example.com','password':'LightingOnly@123'}).status_code==200
        assert c.get('/api/v1/products?workspace=LIGHTING').status_code==200
        assert c.get('/api/v1/products?workspace=AUTOMATION').status_code==403


def test_release5_category_cycle_and_typed_spec_validation():
    with TestClient(app) as c:
        assert c.post('/api/v1/auth/login',json={'email':'fixture-admin@example.com','password':'Admin@12345'}).status_code==200
        root=c.post('/api/v1/catalogue/categories',headers=csrf(c),json={'workspace':'LIGHTING','name':'Release 5 Root'})
        assert root.status_code==200,root.text
        assert c.post('/api/v1/catalogue/categories',headers=csrf(c),json={'workspace':'LIGHTING','name':'release 5 root'}).status_code==409
        child=c.post('/api/v1/catalogue/categories',headers=csrf(c),json={'workspace':'LIGHTING','name':'Release 5 Child','parent_id':root.json()['id']})
        assert child.status_code==200,child.text
        cycle=c.patch(f"/api/v1/catalogue/categories/{root.json()['id']}",headers=csrf(c),json={'workspace':'LIGHTING','name':'Release 5 Root','parent_id':child.json()['id']})
        assert cycle.status_code==422
        family=c.post('/api/v1/product-families',headers=csrf(c),json={'workspace':'LIGHTING','category_id':child.json()['id'],'name':'Release 5 Family','brand':'AlphaNumeric'})
        assert family.status_code==200
        definition=c.post('/api/v1/specification-definitions',headers=csrf(c),json={'workspace':'LIGHTING','category_id':child.json()['id'],'product_family_id':family.json()['id'],'spec_key':'wattage','label':'Wattage','help_text':'Rated input power','data_type':'measurement','unit':'W','allowed_units':['W','kW'],'min_value':1,'max_value':100,'precision':1,'required':True,'show_in_room_picker':True,'show_in_exports':True,'searchable':True,'sort_order':1})
        assert definition.status_code==200,definition.text
        definitions=c.get(f"/api/v1/specification-definitions?workspace=LIGHTING&category_id={child.json()['id']}&family_id={family.json()['id']}").json()
        assert definitions[0]['help_text']=='Rated input power' and definitions[0]['allowed_units']==['W','kW']
        variant=c.post(f"/api/v1/product-families/{family.json()['id']}/variants",headers=csrf(c),json={'sku':'REL5-SPEC-001','name':'Release 5 Variant','price':100})
        assert variant.status_code==422
        variant=c.post(f"/api/v1/product-families/{family.json()['id']}/variants",headers=csrf(c),json={'sku':'REL5-SPEC-002','name':'Release 5 Variant','price':100,'specs':{'wattage':20}})
        assert variant.status_code==200,variant.text
        stored=c.put(f"/api/v1/product-variants/{variant.json()['id']}/specifications",headers=csrf(c),json={'values':{'wattage':{'amount':20,'unit':'W'}}})
        assert stored.status_code==200 and stored.json()['values']['wattage']['value']['amount']=='20.0'
        assert c.put(f"/api/v1/product-variants/{variant.json()['id']}/specifications",headers=csrf(c),json={'values':{'wattage':{'amount':101,'unit':'W'}}}).status_code==422
        assert c.put(f"/api/v1/product-variants/{variant.json()['id']}/specifications",headers=csrf(c),json={'values':{'wattage':{'amount':20,'unit':'VA'}}}).status_code==422


def test_release5_customer_invitation_reuse_and_single_use():
    from urllib.parse import parse_qs, urlparse
    with TestClient(app) as c:
        assert c.post('/api/v1/auth/login',json={'email':'fixture-admin@example.com','password':'Admin@12345'}).status_code==200
        inquiry=c.get('/api/v1/inquiries?workspace=LIGHTING').json()[0]
        payload={'contact_name':'Portal Customer','email':'portal.release5@example.com','phone':'9000000001','customer_role':'CUSTOMER','application_access':['LIGHTING'],'send_invitation':False}
        invite=c.post(f"/api/v1/inquiries/{inquiry['id']}/customer-invitations",headers=csrf(c),json=payload)
        assert invite.status_code==200,invite.text
        token=parse_qs(urlparse(invite.json()['activation_link']).query)['token'][0]
        accepted=c.post('/api/v1/auth/activate-invitation',json={'token':token,'password':'PortalSecure@123'})
        assert accepted.status_code==200
        assert c.post('/api/v1/auth/activate-invitation',json={'token':token,'password':'PortalSecure@123'}).status_code==409
        assert c.post('/api/v1/auth/login',json={'email':'portal.release5@example.com','password':'PortalSecure@123'}).status_code==200
        assert c.post('/api/v1/auth/login',json={'email':'fixture-admin@example.com','password':'Admin@12345'}).status_code==200
        assert c.post(f"/api/v1/inquiries/{inquiry['id']}/customer-invitations",headers=csrf(c),json=payload).status_code==409
        reused=c.post(f"/api/v1/inquiries/{inquiry['id']}/customer-invitations",headers=csrf(c),json={**payload,'confirm_existing_user':True})
        assert reused.status_code==200 and reused.json()['user_reused'] is True and reused.json()['activation_link'] is None
        assert c.post('/api/v1/auth/login',json={'email':'portal.release5@example.com','password':'PortalSecure@123'}).status_code==200


def test_release5_media_dedup_and_project_authorization():
    image = solid_png((90, 120, 160))
    with TestClient(app) as c:
        assert c.post('/api/v1/auth/login',json={'email':'fixture-admin@example.com','password':'Admin@12345'}).status_code==200
        product=c.get('/api/v1/products?workspace=LIGHTING').json()[0]
        first=c.post(f"/api/v1/product-variants/{product['id']}/images",headers=csrf(c),files={'file':('dedup.png',image,'image/png')},data={'alt_text':'Dedup fixture'})
        assert first.status_code==200,first.text
        duplicate=c.post(f"/api/v1/product-variants/{product['id']}/images",headers=csrf(c),files={'file':('same.png',image,'image/png')},data={'alt_text':'Same bytes'})
        assert duplicate.status_code==409
        assert c.post('/api/v1/auth/login',json={'email':'lighting5@example.com','password':'LightingOnly@123'}).status_code==200
        assert c.get(first.json()['url']).status_code==403


def test_release5_invitation_building_scope_is_enforced():
    from urllib.parse import parse_qs, urlparse
    with TestClient(app) as c:
        assert c.post('/api/v1/auth/login',json={'email':'fixture-admin@example.com','password':'Admin@12345'}).status_code==200
        inquiry=c.get('/api/v1/inquiries?workspace=LIGHTING').json()[0]
        project_id=inquiry['project']['id']
        buildings=c.get(f'/api/v1/projects/{project_id}/buildings').json()
        allowed=buildings[0]
        blocked=c.post(f'/api/v1/projects/{project_id}/buildings',headers=csrf(c),json={'name':'Restricted Building Fixture'})
        assert blocked.status_code==200,blocked.text
        invitation=c.post(f"/api/v1/inquiries/{inquiry['id']}/customer-invitations",headers=csrf(c),json={
            'contact_name':'Building Scoped User','email':'building.scope@example.com','customer_role':'CUSTOMER',
            'application_access':['LIGHTING'],'send_invitation':False,'building_id':allowed['id']})
        assert invitation.status_code==200,invitation.text
        token=parse_qs(urlparse(invitation.json()['activation_link']).query)['token'][0]
        assert c.post('/api/v1/auth/activate-invitation',json={'token':token,'password':'BuildingScope@123'}).status_code==200
        assert c.post('/api/v1/auth/login',json={'email':'building.scope@example.com','password':'BuildingScope@123'}).status_code==200
        visible=c.get(f'/api/v1/projects/{project_id}/buildings').json()
        assert [row['id'] for row in visible]==[allowed['id']]
        assert c.get(f"/api/v1/projects/{project_id}/buildings/{blocked.json()['id']}").status_code==403


def test_release5_invitation_invalid_expired_revoked_and_resend_rotation():
    from datetime import datetime, timedelta, timezone
    from urllib.parse import parse_qs, urlparse
    from app import models as m
    with TestClient(app) as c:
        assert c.post('/api/v1/auth/login',json={'email':'fixture-admin@example.com','password':'Admin@12345'}).status_code==200
        inquiry=c.get('/api/v1/inquiries?workspace=LIGHTING').json()[0]
        base={'contact_name':'Invitation States','phone':'9000000002','customer_role':'CUSTOMER','application_access':['LIGHTING'],'send_invitation':False}
        assert c.post('/api/v1/auth/activate-invitation',json={'token':'x'*48,'password':'PortalSecure@123'}).status_code==400

        expired=c.post(f"/api/v1/inquiries/{inquiry['id']}/customer-invitations",headers=csrf(c),json={**base,'email':'expired.release5@example.com'})
        expired_token=parse_qs(urlparse(expired.json()['activation_link']).query)['token'][0]
        with SessionLocal() as db:
            row=db.get(m.CustomerInvitation,expired.json()['id']); row.expires_at=datetime.now(timezone.utc)-timedelta(minutes=1); db.commit()
        assert c.post('/api/v1/auth/activate-invitation',json={'token':expired_token,'password':'PortalSecure@123'}).status_code==410
        resent=c.post(f"/api/v1/customer-invitations/{expired.json()['id']}/resend",headers=csrf(c))
        assert resent.status_code==200
        new_token=parse_qs(urlparse(resent.json()['activation_link']).query)['token'][0]
        assert new_token != expired_token
        assert c.post('/api/v1/auth/activate-invitation',json={'token':expired_token,'password':'PortalSecure@123'}).status_code==400

        revoked=c.post(f"/api/v1/inquiries/{inquiry['id']}/customer-invitations",headers=csrf(c),json={**base,'email':'revoked.release5@example.com'})
        revoked_token=parse_qs(urlparse(revoked.json()['activation_link']).query)['token'][0]
        assert c.post(f"/api/v1/customer-invitations/{revoked.json()['id']}/revoke",headers=csrf(c)).status_code==200
        assert c.post('/api/v1/auth/activate-invitation',json={'token':revoked_token,'password':'PortalSecure@123'}).status_code==409


def test_release5_rejects_malformed_and_cross_application_media_access():
    with TestClient(app) as c:
        assert c.post('/api/v1/auth/login',json={'email':'fixture-admin@example.com','password':'Admin@12345'}).status_code==200
        product=c.get('/api/v1/products?workspace=LIGHTING').json()[0]
        bad=c.post(f"/api/v1/product-variants/{product['id']}/images",headers=csrf(c),files={'file':('renamed.png',b'<html>bad</html>','image/png')},data={'alt_text':'bad'})
        assert bad.status_code==422


def test_release503_category_metadata_security_and_application_isolation():
    with TestClient(app) as c:
        assert c.post('/api/v1/auth/login',json={'email':'fixture-admin@example.com','password':'Admin@12345'}).status_code==200
        created=c.post('/api/v1/catalogue/categories',headers=csrf(c),json={
            'workspace':'LIGHTING','name':'  Architectural   COB  ','slug':'architectural-cob',
            'short_description':'Professional fixtures','full_description':'Safe catalogue description',
            'catalogue_visible':True,'customer_visible':True,'search_visible':True,'status':'DRAFT','sort_order':12})
        assert created.status_code==200,created.text
        assert created.json()['name']=='Architectural COB'
        duplicate=c.post('/api/v1/catalogue/categories',headers=csrf(c),json={
            'workspace':'LIGHTING','name':'Different label','slug':'ARCHITECTURAL-COB','status':'ACTIVE'})
        assert duplicate.status_code==409
        unsafe=c.post('/api/v1/catalogue/categories',headers=csrf(c),json={
            'workspace':'LIGHTING','name':'Unsafe','full_description':'<script>alert(1)</script>'})
        assert unsafe.status_code==422
        tree=c.get('/api/v1/catalogue/categories/tree?workspace=LIGHTING')
        assert tree.status_code==200
        assert any(row['id']==created.json()['id'] and row['slug']=='architectural-cob' for row in tree.json())


def test_release503_catalogue_snapshot_is_immutable_and_pdf_downloads():
    with TestClient(app) as c:
        assert c.post('/api/v1/auth/login',json={'email':'fixture-admin@example.com','password':'Admin@12345'}).status_code==200
        product=c.get('/api/v1/products?workspace=LIGHTING').json()[0]
        original_name=product['name']
        published=c.post('/api/v1/catalogue/versions',headers=csrf(c),json={
            'application':'LIGHTING','name':'Release 5.0.3 Test Catalogue','code':'R503-TEST',
            'version':'1.0','cover_title':'AlphaNumeric Lighting','price_mode':'NONE',
            'product_ids':[product['id']],'include_specifications':True})
        assert published.status_code==200,published.text
        version_id=published.json()['id']
        assert published.json()['status']=='PUBLISHED' and published.json()['product_count']==1
        with SessionLocal() as db:
            row=db.get(__import__('app.models',fromlist=['Product']).Product,product['id'])
            row.name='Changed after publication';db.commit()
            snapshot=db.get(__import__('app.models',fromlist=['CataloguePublication']).CataloguePublication,version_id).snapshot
            assert snapshot['products'][0]['name']==original_name
            row.name=original_name;db.commit()
        pdf=c.get(f'/api/v1/catalogue/versions/{version_id}/pdf')
        assert pdf.status_code==200 and pdf.headers['content-type']=='application/pdf'
        assert len(PdfReader(BytesIO(pdf.content)).pages)>=3
        archive=c.post(f'/api/v1/catalogue/versions/{version_id}/archive',headers=csrf(c))
        assert archive.status_code==200 and archive.json()['status']=='ARCHIVED'


def test_release504_category_edit_drag_reorder_and_cycle_guards():
    with TestClient(app) as c:
        assert c.post('/api/v1/auth/login',json={'email':'fixture-admin@example.com','password':'Admin@12345'}).status_code==200
        first=c.post('/api/v1/catalogue/categories',headers=csrf(c),json={'workspace':'LIGHTING','name':'R504 First','sort_order':80})
        second=c.post('/api/v1/catalogue/categories',headers=csrf(c),json={'workspace':'LIGHTING','name':'R504 Second','sort_order':81})
        child=c.post('/api/v1/catalogue/categories',headers=csrf(c),json={'workspace':'LIGHTING','name':'R504 Child','parent_id':first.json()['id'],'sort_order':0})
        assert first.status_code==second.status_code==child.status_code==200
        edited=c.patch(f"/api/v1/catalogue/categories/{second.json()['id']}",headers=csrf(c),json={
            'workspace':'LIGHTING','name':'R504 Second Edited','slug':'r504-second-edited','sort_order':81,
            'short_description':'Editable category metadata','catalogue_visible':True,'customer_visible':True,'search_visible':True,'status':'ACTIVE'})
        assert edited.status_code==200
        reordered=c.put('/api/v1/catalogue/categories/reorder',headers=csrf(c),json={'workspace':'LIGHTING','items':[
            {'id':second.json()['id'],'parent_id':None,'sort_order':0},{'id':first.json()['id'],'parent_id':None,'sort_order':1}]})
        assert reordered.status_code==200 and reordered.json()['updated']==2
        cycle=c.put('/api/v1/catalogue/categories/reorder',headers=csrf(c),json={'workspace':'LIGHTING','items':[
            {'id':first.json()['id'],'parent_id':child.json()['id'],'sort_order':0}]})
        assert cycle.status_code==422


def test_release504_complete_product_content_and_effective_price_history():
    with TestClient(app) as c:
        assert c.post('/api/v1/auth/login',json={'email':'fixture-admin@example.com','password':'Admin@12345'}).status_code==200
        product=c.get('/api/v1/products?workspace=LIGHTING').json()[0]
        updated=c.patch(f"/api/v1/product-variants/{product['id']}",headers=csrf(c),json={
            'internal_name':'Internal CA1','manufacturer':'AlphaNumeric Industries','barcode':'8901234567890',
            'search_tags':['cob','architectural'], 'full_description':'Sanitized complete product description.',
            'highlights':['CRI above 90','Tool-free installation'],'features':['Low glare'],'applications':['Retail','Hospitality'],
            'installation_summary':'Install in a compatible cut-out.','care_guide':'Clean with a dry cloth.',
            'warranty_summary':'Three-year limited warranty.','internal_notes':'Margin restricted to administrators.',
            'price':1450,'mrp_price':1800,'project_price':1375,'dealer_price':1250,'reseller_price':1200,
            'currency':'INR','minimum_order_quantity':2,'pricing_status':'APPROVED'})
        assert updated.status_code==200,updated.text
        body=updated.json();assert body['barcode']=='8901234567890' and body['highlights'][1]=='Tool-free installation'
        assert body['mrp_price']==1800 and body['dealer_price']==1250 and body['internal_notes'].startswith('Margin')
        history=c.get(f"/api/v1/product-variants/{product['id']}/prices")
        assert history.status_code==200
        assert {'BASE','MRP','PROJECT','DEALER','RESELLER'} <= {row['price_type'] for row in history.json()}
        publication=c.post('/api/v1/catalogue/versions',headers=csrf(c),json={
            'application':'LIGHTING','name':'Release 5.0.4 MRP Catalogue','code':'R504-MRP',
            'version':'1.0','cover_title':'AlphaNumeric Lighting','price_mode':'MRP',
            'product_ids':[product['id']]})
        assert publication.status_code==200,publication.text
        with SessionLocal() as db:
            publication_model=__import__('app.models',fromlist=['CataloguePublication']).CataloguePublication
            snapshot=db.get(publication_model,publication.json()['id']).snapshot
            assert snapshot['products'][0]['price']=='1800.00'
        scheduled=c.post(f"/api/v1/product-variants/{product['id']}/prices",headers=csrf(c),json={
            'price_type':'MRP','amount':1900,'currency':'INR','effective_from':'2030-01-01T00:00:00Z',
            'effective_until':'2030-12-31T23:59:59Z','status':'APPROVED','approval_note':'Approved future list price'})
        assert scheduled.status_code==200,scheduled.text
        overlap=c.post(f"/api/v1/product-variants/{product['id']}/prices",headers=csrf(c),json={
            'price_type':'MRP','amount':1950,'currency':'INR','effective_from':'2030-06-01T00:00:00Z',
            'effective_until':'2031-01-01T00:00:00Z','status':'APPROVED'})
        assert overlap.status_code==409
        unsafe=c.patch(f"/api/v1/product-variants/{product['id']}",headers=csrf(c),json={'full_description':'<script>alert(1)</script>'})
        assert unsafe.status_code==422
        assert c.post('/api/v1/auth/login',json={'email':'user@alphanumeric-demo.com','password':'User@12345'}).status_code==200
        public=c.get(f"/api/v1/products/{product['id']}").json()
        assert 'internal_notes' not in public and 'dealer_price' not in public and 'cost' not in public


def test_release504_arcot_allowlist_dry_run_commit_idempotency_and_no_price(monkeypatch):
    from app import arcot_import
    fixture=[{'source_url':'https://arcotindia.com/products/ca1','name':'CA1 COB Luminaire','model':'CA1',
              'description':'Authorized sanitized source fixture','highlights':['High CRI','Multiple beam angles'],
              'specifications':{'Wattage':'12W','CRI':'>90'},'images':['https://arcotindia.com/media/ca1.jpg'],
              'documents':['https://arcotindia.com/media/ca1.pdf'],'related_urls':[]}]
    monkeypatch.setattr(arcot_import,'discover_products',lambda source:fixture)
    with TestClient(app) as c:
        assert c.post('/api/v1/auth/login',json={'email':'fixture-admin@example.com','password':'Admin@12345'}).status_code==200
        assert c.post('/api/v1/catalogue/arcot/imports',headers=csrf(c),json={'source_url':'http://127.0.0.1/private','rights_confirmed':True}).status_code==422
        assert c.post('/api/v1/catalogue/arcot/imports',headers=csrf(c),json={'source_url':'https://arcotindia.com/cobs-product','rights_confirmed':False}).status_code==422
        category=c.get('/api/v1/categories?workspace=LIGHTING').json()[0]
        dry=c.post('/api/v1/catalogue/arcot/imports',headers=csrf(c),json={'source_url':'https://arcotindia.com/cobs-product','rights_confirmed':True,'dry_run':True})
        assert dry.status_code==200 and dry.json()['rows'][0]['action']=='CREATE_DRAFT' and dry.json()['rows'][0]['price_status']=='PRICE_REQUIRED'
        committed=c.post('/api/v1/catalogue/arcot/imports',headers=csrf(c),json={'source_url':'https://arcotindia.com/cobs-product','rights_confirmed':True,'dry_run':False,'category_id':category['id']})
        assert committed.status_code==200 and committed.json()['imported']==1 and committed.json()['assets_hotlinked'] is False
        product_id=committed.json()['rows'][0]['product_id']; product=c.get(f'/api/v1/products/{product_id}').json()
        assert product['price']==0 and product['pricing_status']=='PRICE_REQUIRED' and product['status']=='DRAFT'
        repeated=c.post('/api/v1/catalogue/arcot/imports',headers=csrf(c),json={'source_url':'https://arcotindia.com/cobs-product','rights_confirmed':True,'dry_run':False,'category_id':category['id']})
        assert repeated.status_code==200 and repeated.json()['imported']==0 and repeated.json()['skipped']==1
        report=c.get(f"/api/v1/catalogue/arcot/imports/{committed.json()['id']}/report.csv")
        assert report.status_code==200 and b'PRICE_REQUIRED' in report.content
