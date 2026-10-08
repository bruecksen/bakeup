from django.db import migrations


def copy_instructions(apps, schema_editor):
    # Production plans keep a copy of the instructions from now on. Plans made
    # before get the instructions their recipe has today.
    Instruction = apps.get_model("workshop", "Instruction")
    ProductionPlan = apps.get_model("workshop", "ProductionPlan")
    products = (
        ProductionPlan.objects.filter(
            product__product_template__instructions__isnull=False,
            product__instructions__isnull=True,
        )
        .values_list("product_id", "product__product_template_id")
        .distinct()
    )
    templates = {
        instruction.product_id: instruction
        for instruction in Instruction.objects.filter(
            product_id__in=[template_id for _, template_id in products]
        )
    }
    Instruction.objects.bulk_create(
        Instruction(
            product_id=product_id,
            instruction=templates[template_id].instruction,
            duration=templates[template_id].duration,
        )
        for product_id, template_id in products
        if template_id in templates
    )


class Migration(migrations.Migration):
    dependencies = [
        ("workshop", "0010_productionplan_checked_ingredients"),
    ]

    operations = [
        migrations.RunPython(copy_instructions, migrations.RunPython.noop),
    ]
