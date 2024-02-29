#!/bin/sh
python manage.py tenant_command dumpdata --all --schema=localhost shop.PointOfSale > bakeup/shop/fixtures/demo_point_of_sale.json
python manage.py tenant_command dumpdata --all --schema=localhost users auth shop.Customer > bakeup/users/fixtures/demo_users.json
python manage.py tenant_command dumpdata --all --schema=localhost workshop.Category > bakeup/workshop/fixtures/demo_categories.json
python manage.py tenant_command dumpdata --all --schema=localhost workshop.Product workshop.ProductHierarchy workshop.Instruction taggit.Tag taggit.TaggedItem > bakeup/workshop/fixtures/demo_products.json
