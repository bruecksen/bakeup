# Generated by Django 3.2.12 on 2023-04-20 13:23

from django.db import migrations


def create_initial_menu(apps, schema_editor):
    MainMenu = apps.get_model("wagtailmenus", "MainMenu")
    MainMenuItem = apps.get_model("wagtailmenus", "MainMenuItem")
    Site = apps.get_model("wagtailcore.Site")
    current_site = Site.objects.get(is_default_site=True)
    main_menu, created = MainMenu.objects.get_or_create(site=current_site)
    main_menu_item = MainMenuItem(
        menu=main_menu,
        sort_order=1,
        allow_subnav=False,
        link_url='/shop/',
        link_text='Shop',
        handle='shop'
    )
    main_menu_item.save()
    main_menu_item = MainMenuItem(
        menu=main_menu,
        sort_order=2,
        allow_subnav=False,
        link_url='/shop/backtage/',
        link_text='Backtage',
        handle='production-days',
    )
    main_menu_item.save()
    main_menu_item = MainMenuItem(
        menu=main_menu,
        sort_order=3,
        allow_subnav=False,
        link_url='/shop/sortiment/',
        link_text='Sortiment',
        handle='product-list',
    )
    main_menu_item.save()
    main_menu_item = MainMenuItem(
        menu=main_menu,
        sort_order=4,
        allow_subnav=False,
        link_url='/shop/bestellungen/',
        link_text='Bestellungen',
        handle='orders',
    )
    main_menu_item.save()
    FlatMenu = apps.get_model("wagtailmenus", "FlatMenu")
    FlatMenuItem = apps.get_model("wagtailmenus", "FlatMenuItem")
    ContentPage = apps.get_model("pages", "ContentPage")
    flat_menu, created = FlatMenu.objects.get_or_create(
        site=current_site,
        handle='footer',
        defaults={
            'title': 'footer',
        }
    )
    flat_menu_item = FlatMenuItem(
        menu=flat_menu,
        sort_order=1,
        allow_subnav=False,
        link_page=ContentPage.objects.get(slug='impressum'),
        link_text='Impressum',
        handle='impressum',
    )
    flat_menu_item.save()
    flat_menu_item = FlatMenuItem(
        menu=flat_menu,
        sort_order=2,
        allow_subnav=False,
        link_page=ContentPage.objects.get(slug='datenschutz'),
        link_text='Datenschutz',
        handle='datenschutz',
    )
    flat_menu_item.save()



    


def remove_initial_menu(apps, schema_editor):
    MainMenuItem = apps.get_model("wagtailmenus", "MainMenuItem")
    MainMenuItem.objects.all().delete()
    FlatMenuItem = apps.get_model("wagtailmenus", "FlatMenuItem")
    FlatMenuItem.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0002_create_initial_pages'),
        ('wagtailmenus', '0024_auto_20230509_0916'),
    ]

    operations = [
        migrations.RunPython(create_initial_menu, remove_initial_menu)
    ]
