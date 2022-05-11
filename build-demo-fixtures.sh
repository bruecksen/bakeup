#!/bin/sh
python manage.py dumpdata workshop.Product workshop.ProductHierarchy workshop.Instruction> bakeup/workshop/fixtures/demo-products.json
python manage.py dumpdata shop.CustomerOrder shop.CustomerOrderPosition shop.ProductionDay shop.ProductionDayProduct workshop.ProductionPlan > bakeup/shop/fixtures/demo_baking_days.json
