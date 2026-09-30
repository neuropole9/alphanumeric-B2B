from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from app import models as m
from app.catalog_api import _natural_model_key, _family_out
from app.db import Base, SessionLocal, engine
from app.main import app
from app.release5_api import InvitationIn
from scripts.import_cob_variant_images import import_images, bundled_images_dir
from scripts.check_cob_models import check_models
from pathlib import Path
from uuid import uuid4
from tests.seed_fixture import seed

Base.metadata.create_all(bind=engine)
with SessionLocal() as db:
    seed(db)


def test_variant_patch_decimal_null_and_validation_response():
    with TestClient(app) as client:
        assert client.post('/api/v1/auth/login', json={'email':'fixture-admin@example.com','password':'Admin@12345'}).status_code == 200
        headers = {'X-CSRF-Token': client.cookies.get('csrf_token')}
        with SessionLocal() as db:
            family = db.scalars(select(m.ProductFamily).where(
                m.ProductFamily.workspace == 'LIGHTING', m.ProductFamily.name != 'LED Panel Light')).first()
        created = client.post(f'/api/v1/product-families/{family.id}/variants', headers=headers,
                              json={'sku':f'RELEASE506-PATCH-{uuid4().hex}','name':'Test model','price':'100.25'})
        assert created.status_code == 200, created.text
        product_id = created.json()['id']
        spec_key = f'input_voltage_{uuid4().hex[:8]}'
        with SessionLocal() as db:
            product = db.get(m.Product, product_id)
            db.add(m.ProductSpecDefinition(workspace='LIGHTING', category_id=product.category_id,
                                           product_family_id=family.id, spec_key=spec_key,
                                           label='Input Voltage', data_type='text', status='ACTIVE'))
            db.add(m.ProductSpecDefinition(workspace='LIGHTING', category_id=product.category_id,
                                           product_family_id=family.id, spec_key=f'archived_{uuid4().hex[:8]}',
                                           label='Archived Field', data_type='text', required=True,
                                           status='ARCHIVED'))
            product.specs = {spec_key:'220-240V AC',
                             'source_url':'https://example.com/legacy-catalogue-record'}
            db.commit()
        payload = {'name':'Updated test model','price':'100.25','cost':None,'mrp_price':None,
                   'project_price':'90.05','dealer_price':'0','reseller_price':None,
                   'minimum_order_quantity':'0.25','tax_rate':'18.50','reorder_level':'0',
                   'lead_time_days':0,'search_tags':['COB','DALI DT8'],
                   'highlights':['First line','Second line'],
                   'specs': {spec_key:'220-240V AC',
                             'source_url':'https://example.com/legacy-catalogue-record'}}
        good = client.patch(f'/api/v1/product-variants/{product_id}',headers=headers,json=payload)
        assert good.status_code == 200, good.text
        assert good.json()['project_price'] == 90.05
        with SessionLocal() as db:
            row = db.get(m.Product, product_id)
            assert row.price == Decimal('100.25') and row.minimum_order_quantity == Decimal('0.25')
            assert row.cost is None and row.lead_time_days == 0 and row.search_tags == ['COB','DALI DT8']
        assert row.specs == payload['specs']
        without_provenance = client.patch(f'/api/v1/product-variants/{product_id}', headers=headers,
                                          json={'specs': {spec_key: '220-240V AC'}})
        assert without_provenance.status_code == 200, without_provenance.text
        assert without_provenance.json()['specs']['source_url'] == payload['specs']['source_url']
        invalid = client.patch(f'/api/v1/product-variants/{product_id}',headers=headers,json={'cost':''})
        assert invalid.status_code == 422
        error = invalid.json()['detail'][0]
        assert error['loc'] == ['body','cost'] and error['type'] == 'decimal_parsing' and error['input'] == ''
        changed_legacy = client.patch(f'/api/v1/product-variants/{product_id}', headers=headers,
                                      json={'specs': {'source_url':'https://example.com/changed'}})
        assert changed_legacy.status_code == 422
        assert 'Unknown specification keys' in changed_legacy.json()['detail']


def test_invitation_roles_and_natural_models():
    base = {'contact_name':'Tester','email':'tester@example.com','application_access':['LIGHTING']}
    for source, expected in [('Customer','CUSTOMER'),('customer','CUSTOMER'),
                             ('Project User','PROJECT_USER'),('project-user','PROJECT_USER')]:
        assert InvitationIn.model_validate({**base,'customer_role':source}).customer_role == expected
    for role in ('ADMIN','SUPER_ADMIN','CUSTOMER_APPROVER'):
        try:
            InvitationIn.model_validate({**base,'customer_role':role})
        except ValueError:
            pass
        else:
            raise AssertionError(f'{role} must not be accepted')
    assert sorted(['CA10','CA2','CA1'], key=_natural_model_key) == ['CA1','CA2','CA10']


def test_bundled_cob_images_map_to_exact_variants(tmp_path):
    images = Path(__file__).resolve().parents[2] / 'Images'
    assert bundled_images_dir() == images
    with SessionLocal() as db:
        family = db.scalars(select(m.ProductFamily).where(m.ProductFamily.workspace == 'LIGHTING')).first()
        for model in (f'CA{number}' for number in range(1, 11)):
            db.add(m.Product(workspace='LIGHTING',category_id=family.category_id,family_id=family.id,
                             sku=f'ARCOT-COB-{model}',model_number=model,name=model,variant_name=model,
                             price=Decimal('0'),tax_rate=Decimal('18'),specs={}))
        db.flush()
        results=import_images(db,images,tmp_path,apply=True)
        db.flush()
        for model in (f'CA{number}' for number in range(1, 11)):
            assert next(x for x in results if x['model']==model)['status']=='registered'
            product=db.scalar(select(m.Product).where(m.Product.sku==f'ARCOT-COB-{model}'))
            media=db.scalar(select(m.ProductMedia).where(m.ProductMedia.product_id==product.id))
            assert media.is_primary and media.original_filename==f'{model}.webp'
            assert (tmp_path/media.storage_key).read_bytes()==(images/f'{model}.webp').read_bytes()
        db.expire_all()
        admin=db.scalar(select(m.User).where(m.User.role=='ADMIN'))
        rendered=_family_out(db,db.get(m.ProductFamily,family.id),admin,detailed=True)
        models=[item['model_number'] for item in rendered['variants'] if item['model_number'] and item['model_number'].startswith('CA')]
        assert models==[f'CA{number}' for number in range(1,11)]
        assert len({item['primary_image_url'] for item in rendered['variants'] if item['model_number'] in models})==10
        assert [row['image'] for row in check_models(db,tmp_path)] == ['ready'] * 10
        db.rollback()
