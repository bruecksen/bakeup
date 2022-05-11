#!/bin/sh
python manage.py dumpdata workshop.Product workshop.ProductHierarchy workshop.Instruction> bakeup/workshop/fixtures/demo-products.json
