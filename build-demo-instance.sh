#!/bin/sh
python manage.py delete_tenant --schema=demo --noinput
python manage.py create_tenant --noinput --schema_name=demo --name="Bakeup Demo" --is_demo=True --domain-domain=demo.bakeup.org --domain-is_primary=True
python manage.py tenant_command loaddata --schema=demo bakeup/shop/fixtures/demo_point_of_sale.json
python manage.py tenant_command loaddata --schema=demo bakeup/users/fixtures/demo_users.json
python manage.py tenant_command loaddata --schema=demo bakeup/workshop/fixtures/demo_categories.json
python manage.py tenant_command loaddata --schema=demo bakeup/workshop/fixtures/demo_products.json
python manage.py create_initial_demo_wagtail_pages --schema=demo --noinput
