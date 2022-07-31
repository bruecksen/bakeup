#!/bin/sh
python manage.py dumpdata --all users > bakeup/users/fixtures/demo-data.json   
python manage.py dumpdata --all shop.Customer shop.PointOfSale core.Address > bakeup/shop/fixtures/demo_customers.json
python manage.py dumpdata --all workshop.Category > bakeup/workshop/fixtures/categories.json  
python manage.py dumpdata --all workshop.Product workshop.ProductHierarchy workshop.Instruction> bakeup/workshop/fixtures/demo-products.json
python manage.py dumpdata --all shop.CustomerOrder shop.CustomerOrderPosition shop.ProductionDay shop.ProductionDayProduct workshop.ProductionPlan > bakeup/shop/fixtures/demo_baking_days.json
