#!/bin/sh
python manage.py create_tenant
python manage.py tenant_command loaddata --schema=localhost bakeup/shop/fixtures/demo_point_of_sale.json
python manage.py tenant_command loaddata --schema=localhost bakeup/users/fixtures/demo_users.json
python manage.py tenant_command loaddata --schema=localhost bakeup/workshop/fixtures/demo_categories.json
python manage.py tenant_command loaddata --schema=localhost bakeup/workshop/fixtures/demo_products.json
python manage.py create_initial_demo_wagtail_pages
