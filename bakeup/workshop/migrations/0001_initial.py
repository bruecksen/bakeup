# Generated by Django 3.2.12 on 2022-03-24 09:49

from django.db import migrations, models
import django.db.models.deletion
import django.db.models.expressions


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('is_archived', models.BooleanField(default=False)),
                ('name', models.CharField(max_length=255)),
                ('slug', models.SlugField()),
                ('image', models.FileField(upload_to='')),
                ('description', models.TextField()),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='workshop.category')),
            ],
        ),
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('is_archived', models.BooleanField(default=False)),
                ('name', models.CharField(max_length=255)),
                ('slug', models.SlugField()),
                ('description', models.TextField()),
                ('image', models.FileField(upload_to='')),
                ('weight', models.PositiveSmallIntegerField(blank=True, help_text='weight in grams', null=True)),
                ('weight_units', models.CharField(blank=True, choices=[('g', 'Grams'), ('kg', 'Kilograms')], max_length=255, null=True)),
                ('volume', models.PositiveSmallIntegerField(blank=True, help_text='weight in grams', null=True)),
                ('volume_units', models.CharField(blank=True, choices=[('ml', 'Milliliter'), ('l', 'Liter')], max_length=255, null=True)),
                ('is_sellable', models.BooleanField(default=False)),
                ('is_buyable', models.BooleanField(default=False)),
                ('is_composable', models.BooleanField(default=False)),
                ('categories', models.ManyToManyField(to='workshop.Category')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ProductRevision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('is_archived', models.BooleanField(default=False)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('from_date', models.DateTimeField()),
                ('to_date', models.DateTimeField()),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='revisions', to='workshop.product')),
            ],
            options={
                'ordering': ('-timestamp',),
                'unique_together': {('product', 'timestamp')},
            },
        ),
        migrations.CreateModel(
            name='ProductionPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('is_archived', models.BooleanField(default=False)),
                ('start_date', models.DateTimeField()),
                ('quantity', models.PositiveSmallIntegerField()),
                ('duration', models.PositiveSmallIntegerField()),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='production_plans', to='workshop.productrevision')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ProductHierarchy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('is_archived', models.BooleanField(default=False)),
                ('quantity', models.PositiveSmallIntegerField()),
                ('child', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='childs', to='workshop.product')),
                ('parent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='parents', to='workshop.product')),
            ],
        ),
        migrations.CreateModel(
            name='Instruction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('is_archived', models.BooleanField(default=False)),
                ('instruction', models.TextField()),
                ('duration', models.PositiveSmallIntegerField(help_text='duration in seconds')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='instructions', to='workshop.product')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddConstraint(
            model_name='producthierarchy',
            constraint=models.CheckConstraint(check=models.Q(('parent', django.db.models.expressions.F('child')), _negated=True), name='recipe_parent_and_child_cannot_be_equal'),
        ),
        migrations.AlterUniqueTogether(
            name='producthierarchy',
            unique_together={('parent', 'child')},
        ),
        migrations.AddConstraint(
            model_name='category',
            constraint=models.CheckConstraint(check=models.Q(('parent', django.db.models.expressions.F('id')), _negated=True), name='category_id_and_parent_not_equal'),
        ),
    ]
