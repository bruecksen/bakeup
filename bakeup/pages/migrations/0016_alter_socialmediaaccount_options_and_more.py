# Generated by Django 4.2.11 on 2025-03-24 18:41

from django.db import migrations
import django.db.models.deletion
import modelcluster.fields
import wagtail.fields


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0015_alter_contentpage_content_and_more"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="socialmediaaccount",
            options={
                "verbose_name": "Social Media Account",
                "verbose_name_plural": "Social Media Accounts",
            },
        ),
        migrations.AlterField(
            model_name="contentpage",
            name="content",
            field=wagtail.fields.StreamField(
                [
                    ("column11", 35),
                    ("column111", 36),
                    ("column12", 35),
                    ("column21", 35),
                    ("text", 2),
                    ("image", 13),
                    ("button", 17),
                    ("video", 18),
                    ("html", 19),
                    ("space", 21),
                    ("card", 24),
                    ("hr", 25),
                    ("carousel", 28),
                    ("newsletter", 33),
                    ("production_days", 40),
                    ("product_assortment", 42),
                ],
                blank=True,
                block_lookup={
                    0: (
                        "wagtail.blocks.ChoiceBlock",
                        [],
                        {
                            "choices": [
                                ("start", "Left"),
                                ("center", "Centre"),
                                ("end", "Right"),
                                ("justify", "Justified"),
                            ],
                            "label": "Text Alignment",
                        },
                    ),
                    1: ("wagtail.blocks.RichTextBlock", (), {}),
                    2: (
                        "wagtail.blocks.StructBlock",
                        [[("alignment", 0), ("text", 1)]],
                        {"group": "Common"},
                    ),
                    3: ("wagtail.images.blocks.ImageChooserBlock", (), {}),
                    4: (
                        "wagtail.blocks.IntegerBlock",
                        (),
                        {
                            "help_text": "Set a maximum width for the image in pixels.",
                            "min_value": 0,
                            "required": False,
                        },
                    ),
                    5: (
                        "wagtail.blocks.ChoiceBlock",
                        [],
                        {
                            "choices": [
                                ("start", "Left"),
                                ("center", "Centre"),
                                ("end", "Right"),
                            ]
                        },
                    ),
                    6: (
                        "wagtail.blocks.PageChooserBlock",
                        (),
                        {"icon": "doc-empty-inverse", "label": "Page"},
                    ),
                    7: (
                        "wagtail.documents.blocks.DocumentChooserBlock",
                        (),
                        {"icon": "doc-full", "label": "Document"},
                    ),
                    8: ("wagtail.blocks.CharBlock", (), {"label": "Internal link"}),
                    9: ("wagtail.blocks.URLBlock", (), {"label": "External link"}),
                    10: (
                        "wagtail.blocks.CharBlock",
                        (),
                        {
                            "help_text": "An anchor in the current page, for example: <code>#target-id</code>.",
                            "label": "Anchor link",
                        },
                    ),
                    11: (
                        "wagtail.blocks.StreamBlock",
                        [
                            [
                                ("page", 6),
                                ("document", 7),
                                ("link", 8),
                                ("url", 9),
                                ("anchor", 10),
                            ]
                        ],
                        {"required": False},
                    ),
                    12: (
                        "wagtail.blocks.StructBlock",
                        [[("target", 11)]],
                        {"required": False},
                    ),
                    13: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("image", 3),
                                ("max_width", 4),
                                ("alignment", 5),
                                ("link", 12),
                            ]
                        ],
                        {"group": "Common"},
                    ),
                    14: ("wagtail.blocks.CharBlock", (), {"label": "Text"}),
                    15: (
                        "wagtail.blocks.StreamBlock",
                        [
                            [
                                ("page", 6),
                                ("document", 7),
                                ("link", 8),
                                ("url", 9),
                                ("anchor", 10),
                            ]
                        ],
                        {"required": True},
                    ),
                    16: (
                        "wagtail.blocks.StructBlock",
                        [[("target", 15)]],
                        {"required": True},
                    ),
                    17: (
                        "wagtail.blocks.StructBlock",
                        [[("text", 14), ("link", 16)]],
                        {"group": "Common"},
                    ),
                    18: ("bakeup.pages.blocks.EmbedBlock", (), {"group": "Common"}),
                    19: ("wagtail.blocks.RawHTMLBlock", (), {"group": "Common"}),
                    20: (
                        "wagtail.blocks.ChoiceBlock",
                        [],
                        {
                            "choices": [
                                (0, "0"),
                                (1, "16px"),
                                (2, "32px"),
                                (3, "48px"),
                                (4, "64px"),
                            ]
                        },
                    ),
                    21: (
                        "wagtail.blocks.StructBlock",
                        [[("space", 20), ("space_mobile", 20)]],
                        {"group": "Common"},
                    ),
                    22: (
                        "wagtail.blocks.ChoiceBlock",
                        [],
                        {
                            "choices": [
                                ("primary", "Primary"),
                                ("secondary", "Secondary"),
                                ("success", "Green"),
                                ("danger", "Red"),
                                ("warning", "Yellow"),
                                ("info", "Blue"),
                                ("light", "Light"),
                                ("dark", "Dark"),
                            ],
                            "label": "Card Background Colour",
                        },
                    ),
                    23: (
                        "wagtail.blocks.StructBlock",
                        [[("alignment", 0), ("text", 1)]],
                        {
                            "help_text": "Body text for this card.",
                            "label": "Card Body Text",
                        },
                    ),
                    24: (
                        "wagtail.blocks.StructBlock",
                        [[("background", 22), ("text", 23)]],
                        {"group": "Common"},
                    ),
                    25: ("wagtail.blocks.StructBlock", [[]], {"group": "Common"}),
                    26: (
                        "wagtail.blocks.StructBlock",
                        [[("image", 3), ("caption", 1)]],
                        {},
                    ),
                    27: ("wagtail.blocks.ListBlock", (26,), {}),
                    28: (
                        "wagtail.blocks.StructBlock",
                        [[("items", 27)]],
                        {"group": "Common"},
                    ),
                    29: (
                        "wagtail.blocks.CharBlock",
                        (),
                        {"default": "Abonniere unseren Newsletter", "required": False},
                    ),
                    30: (
                        "wagtail.blocks.RichTextBlock",
                        (),
                        {
                            "features": [
                                "h1",
                                "h2",
                                "h3",
                                "bold",
                                "italic",
                                "link",
                                "hr",
                                "ol",
                                "ul",
                                "blockquote",
                                "code",
                            ]
                        },
                    ),
                    31: (
                        "wagtail.blocks.StructBlock",
                        [[("alignment", 0), ("text", 30)]],
                        {
                            "default": "Erhalte die neuesten Updates und Angebote direkt in dein Postfach."
                        },
                    ),
                    32: ("wagtail.blocks.CharBlock", (), {"default": "Abonnieren"}),
                    33: (
                        "wagtail.blocks.StructBlock",
                        [[("heading", 29), ("text", 31), ("button_text", 32)]],
                        {"group": "Common"},
                    ),
                    34: (
                        "wagtail.blocks.StreamBlock",
                        [
                            [
                                ("text", 2),
                                ("image", 13),
                                ("button", 17),
                                ("video", 18),
                                ("html", 19),
                                ("space", 21),
                                ("card", 24),
                                ("hr", 25),
                                ("carousel", 28),
                                ("newsletter", 33),
                            ]
                        ],
                        {"required": False},
                    ),
                    35: (
                        "wagtail.blocks.StructBlock",
                        [[("left", 34), ("right", 34)]],
                        {"group": "Columns"},
                    ),
                    36: (
                        "wagtail.blocks.StructBlock",
                        [[("left", 34), ("middle", 34), ("right", 34)]],
                        {"group": "Columns"},
                    ),
                    37: (
                        "wagtail.blocks.IntegerBlock",
                        (),
                        {"default": 4, "required": False},
                    ),
                    38: (
                        "wagtail.blocks.StructBlock",
                        [[("alignment", 0), ("text", 1)]],
                        {
                            "help_text": "This text is displayed if no production day is planned.",
                            "required": False,
                        },
                    ),
                    39: (
                        "wagtail.blocks.CharBlock",
                        (),
                        {
                            "default": "Zum Backtag",
                            "label": "Button Text (Zum Backtag)",
                            "required": False,
                        },
                    ),
                    40: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("production_day_limit", 37),
                                ("text_no_production_day", 38),
                                ("cta_button_text", 39),
                            ]
                        ],
                        {"group": "Bakeup"},
                    ),
                    41: (
                        "wagtail.blocks.BooleanBlock",
                        (),
                        {"default": True, "required": False},
                    ),
                    42: (
                        "wagtail.blocks.StructBlock",
                        [[("only_planned_products", 41)]],
                        {"group": "Bakeup"},
                    ),
                },
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="shoppage",
            name="content",
            field=wagtail.fields.StreamField(
                [
                    ("column11", 35),
                    ("column111", 36),
                    ("column12", 35),
                    ("column21", 35),
                    ("text", 2),
                    ("image", 13),
                    ("button", 17),
                    ("video", 18),
                    ("html", 19),
                    ("space", 21),
                    ("card", 24),
                    ("hr", 25),
                    ("carousel", 28),
                    ("newsletter", 33),
                    ("production_days", 40),
                    ("product_assortment", 42),
                ],
                blank=True,
                block_lookup={
                    0: (
                        "wagtail.blocks.ChoiceBlock",
                        [],
                        {
                            "choices": [
                                ("start", "Left"),
                                ("center", "Centre"),
                                ("end", "Right"),
                                ("justify", "Justified"),
                            ],
                            "label": "Text Alignment",
                        },
                    ),
                    1: ("wagtail.blocks.RichTextBlock", (), {}),
                    2: (
                        "wagtail.blocks.StructBlock",
                        [[("alignment", 0), ("text", 1)]],
                        {"group": "Common"},
                    ),
                    3: ("wagtail.images.blocks.ImageChooserBlock", (), {}),
                    4: (
                        "wagtail.blocks.IntegerBlock",
                        (),
                        {
                            "help_text": "Set a maximum width for the image in pixels.",
                            "min_value": 0,
                            "required": False,
                        },
                    ),
                    5: (
                        "wagtail.blocks.ChoiceBlock",
                        [],
                        {
                            "choices": [
                                ("start", "Left"),
                                ("center", "Centre"),
                                ("end", "Right"),
                            ]
                        },
                    ),
                    6: (
                        "wagtail.blocks.PageChooserBlock",
                        (),
                        {"icon": "doc-empty-inverse", "label": "Page"},
                    ),
                    7: (
                        "wagtail.documents.blocks.DocumentChooserBlock",
                        (),
                        {"icon": "doc-full", "label": "Document"},
                    ),
                    8: ("wagtail.blocks.CharBlock", (), {"label": "Internal link"}),
                    9: ("wagtail.blocks.URLBlock", (), {"label": "External link"}),
                    10: (
                        "wagtail.blocks.CharBlock",
                        (),
                        {
                            "help_text": "An anchor in the current page, for example: <code>#target-id</code>.",
                            "label": "Anchor link",
                        },
                    ),
                    11: (
                        "wagtail.blocks.StreamBlock",
                        [
                            [
                                ("page", 6),
                                ("document", 7),
                                ("link", 8),
                                ("url", 9),
                                ("anchor", 10),
                            ]
                        ],
                        {"required": False},
                    ),
                    12: (
                        "wagtail.blocks.StructBlock",
                        [[("target", 11)]],
                        {"required": False},
                    ),
                    13: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("image", 3),
                                ("max_width", 4),
                                ("alignment", 5),
                                ("link", 12),
                            ]
                        ],
                        {"group": "Common"},
                    ),
                    14: ("wagtail.blocks.CharBlock", (), {"label": "Text"}),
                    15: (
                        "wagtail.blocks.StreamBlock",
                        [
                            [
                                ("page", 6),
                                ("document", 7),
                                ("link", 8),
                                ("url", 9),
                                ("anchor", 10),
                            ]
                        ],
                        {"required": True},
                    ),
                    16: (
                        "wagtail.blocks.StructBlock",
                        [[("target", 15)]],
                        {"required": True},
                    ),
                    17: (
                        "wagtail.blocks.StructBlock",
                        [[("text", 14), ("link", 16)]],
                        {"group": "Common"},
                    ),
                    18: ("bakeup.pages.blocks.EmbedBlock", (), {"group": "Common"}),
                    19: ("wagtail.blocks.RawHTMLBlock", (), {"group": "Common"}),
                    20: (
                        "wagtail.blocks.ChoiceBlock",
                        [],
                        {
                            "choices": [
                                (0, "0"),
                                (1, "16px"),
                                (2, "32px"),
                                (3, "48px"),
                                (4, "64px"),
                            ]
                        },
                    ),
                    21: (
                        "wagtail.blocks.StructBlock",
                        [[("space", 20), ("space_mobile", 20)]],
                        {"group": "Common"},
                    ),
                    22: (
                        "wagtail.blocks.ChoiceBlock",
                        [],
                        {
                            "choices": [
                                ("primary", "Primary"),
                                ("secondary", "Secondary"),
                                ("success", "Green"),
                                ("danger", "Red"),
                                ("warning", "Yellow"),
                                ("info", "Blue"),
                                ("light", "Light"),
                                ("dark", "Dark"),
                            ],
                            "label": "Card Background Colour",
                        },
                    ),
                    23: (
                        "wagtail.blocks.StructBlock",
                        [[("alignment", 0), ("text", 1)]],
                        {
                            "help_text": "Body text for this card.",
                            "label": "Card Body Text",
                        },
                    ),
                    24: (
                        "wagtail.blocks.StructBlock",
                        [[("background", 22), ("text", 23)]],
                        {"group": "Common"},
                    ),
                    25: ("wagtail.blocks.StructBlock", [[]], {"group": "Common"}),
                    26: (
                        "wagtail.blocks.StructBlock",
                        [[("image", 3), ("caption", 1)]],
                        {},
                    ),
                    27: ("wagtail.blocks.ListBlock", (26,), {}),
                    28: (
                        "wagtail.blocks.StructBlock",
                        [[("items", 27)]],
                        {"group": "Common"},
                    ),
                    29: (
                        "wagtail.blocks.CharBlock",
                        (),
                        {"default": "Abonniere unseren Newsletter", "required": False},
                    ),
                    30: (
                        "wagtail.blocks.RichTextBlock",
                        (),
                        {
                            "features": [
                                "h1",
                                "h2",
                                "h3",
                                "bold",
                                "italic",
                                "link",
                                "hr",
                                "ol",
                                "ul",
                                "blockquote",
                                "code",
                            ]
                        },
                    ),
                    31: (
                        "wagtail.blocks.StructBlock",
                        [[("alignment", 0), ("text", 30)]],
                        {
                            "default": "Erhalte die neuesten Updates und Angebote direkt in dein Postfach."
                        },
                    ),
                    32: ("wagtail.blocks.CharBlock", (), {"default": "Abonnieren"}),
                    33: (
                        "wagtail.blocks.StructBlock",
                        [[("heading", 29), ("text", 31), ("button_text", 32)]],
                        {"group": "Common"},
                    ),
                    34: (
                        "wagtail.blocks.StreamBlock",
                        [
                            [
                                ("text", 2),
                                ("image", 13),
                                ("button", 17),
                                ("video", 18),
                                ("html", 19),
                                ("space", 21),
                                ("card", 24),
                                ("hr", 25),
                                ("carousel", 28),
                                ("newsletter", 33),
                            ]
                        ],
                        {"required": False},
                    ),
                    35: (
                        "wagtail.blocks.StructBlock",
                        [[("left", 34), ("right", 34)]],
                        {"group": "Columns"},
                    ),
                    36: (
                        "wagtail.blocks.StructBlock",
                        [[("left", 34), ("middle", 34), ("right", 34)]],
                        {"group": "Columns"},
                    ),
                    37: (
                        "wagtail.blocks.IntegerBlock",
                        (),
                        {"default": 4, "required": False},
                    ),
                    38: (
                        "wagtail.blocks.StructBlock",
                        [[("alignment", 0), ("text", 1)]],
                        {
                            "help_text": "This text is displayed if no production day is planned.",
                            "required": False,
                        },
                    ),
                    39: (
                        "wagtail.blocks.CharBlock",
                        (),
                        {
                            "default": "Zum Backtag",
                            "label": "Button Text (Zum Backtag)",
                            "required": False,
                        },
                    ),
                    40: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("production_day_limit", 37),
                                ("text_no_production_day", 38),
                                ("cta_button_text", 39),
                            ]
                        ],
                        {"group": "Bakeup"},
                    ),
                    41: (
                        "wagtail.blocks.BooleanBlock",
                        (),
                        {"default": True, "required": False},
                    ),
                    42: (
                        "wagtail.blocks.StructBlock",
                        [[("only_planned_products", 41)]],
                        {"group": "Bakeup"},
                    ),
                },
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="socialmediaaccount",
            name="general_settings",
            field=modelcluster.fields.ParentalKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="social_media_accounts",
                to="pages.generalsettings",
            ),
        ),
    ]
