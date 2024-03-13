#!/bin/sh
/home/django/djangoenv/bin/python /home/django/bakeup/manage.py delete_tenant --schema=demo --noinput --settings=config.settings.production
/home/django/djangoenv/bin/python /home/django/bakeup/manage.py create_tenant --noinput --schema_name=demo --name="Bakeup Demo" --is_demo=True --domain-domain=demo.bakeup.org --domain-is_primary=True --settings=config.settings.production
/home/django/djangoenv/bin/python /home/django/bakeup/manage.py tenant_command loaddata --schema=demo bakeup/shop/fixtures/demo_point_of_sale.json --settings=config.settings.production
/home/django/djangoenv/bin/python /home/django/bakeup/manage.py tenant_command loaddata --schema=demo bakeup/users/fixtures/demo_users.json --settings=config.settings.production
/home/django/djangoenv/bin/python /home/django/bakeup/manage.py tenant_command loaddata --schema=demo bakeup/workshop/fixtures/demo_categories.json --settings=config.settings.production
/home/django/djangoenv/bin/python /home/django/bakeup/manage.py tenant_command loaddata --schema=demo bakeup/workshop/fixtures/demo_products.json --settings=config.settings.production
/home/django/djangoenv/bin/python /home/django/bakeup/manage.py create_initial_demo_wagtail_pages --schema=demo --noinput --settings=config.settings.production
