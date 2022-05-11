#!/bin/sh
python manage.py dumpdata users > bakeup/users/demo-data.json   
python manage.py dumpdata shop.Customer shop.PointOfSale core.Address > bakeup/shop/fixtures/demo_customers.json
python manage.py dumpdata workshop.Category > bakeup/workshop/fixtures/categories.json  
python manage.py dumpdata workshop.Product workshop.ProductHierarchy workshop.Instruction> bakeup/workshop/fixtures/demo-products.json
python manage.py dumpdata shop.CustomerOrder shop.CustomerOrderPosition shop.ProductionDay shop.ProductionDayProduct workshop.ProductionPlan > bakeup/shop/fixtures/demo_baking_days.json
