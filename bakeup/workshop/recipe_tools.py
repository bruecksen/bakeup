from django.apps import apps

# Specific heat capacities in kJ/(kg·K) by category slug, see
# workshop/fixtures/demo_categories.json. A sub category (rye below flour)
# has the value of the nearest category listed here.
HEAT_CAPACITIES = {
    "liquids": 4.19,
    "flour": 1.8,
    "salt": 0.9,
    "sugar": 1.3,
    "fat": 2.0,
}
DEFAULT_HEAT_CAPACITY = 2.0
LIQUIDS_SLUG = "liquids"
WATER_HEAT_CAPACITY = HEAT_CAPACITIES[LIQUIDS_SLUG]


def get_heat_capacity_categories():
    # Slug by tree path of the categories that have a heat capacity. One query,
    # loaded once for all ingredients of a step or of a whole day.
    Category = apps.get_model("workshop", "Category")
    return {
        path: slug
        for slug, path in Category.objects.filter(slug__in=HEAT_CAPACITIES).values_list(
            "slug", "path"
        )
    }


def is_liquid(product, categories):
    # In the liquids category or below it.
    return category_slug(product.category, categories) == LIQUIDS_SLUG


def heat_capacity(product, categories=None):
    if categories is None:
        categories = get_heat_capacity_categories()
    if product.parents.all():
        # A dough that goes into another one, e.g. the pre dough in the main
        # dough: the mean of its ingredients by weight.
        ingredients = product.get_full_ingredient_list()
        total = sum(weight for _ingredient, weight in ingredients)
        if total:
            return (
                sum(
                    weight * category_heat_capacity(ingredient.category, categories)
                    for ingredient, weight in ingredients
                )
                / total
            )
    return category_heat_capacity(product.category, categories)


def category_heat_capacity(category, categories):
    return HEAT_CAPACITIES.get(
        category_slug(category, categories), DEFAULT_HEAT_CAPACITY
    )


def category_slug(category, categories):
    # The slug of the category or of its nearest ancestor among the loaded
    # ones, the path of a treebeard node starts with the paths of its
    # ancestors.
    if category is None:
        return None
    paths = [path for path in categories if category.path.startswith(path)]
    if not paths:
        return None
    return categories[max(paths, key=len)]


def water_temperature(dough, warming, water, others):
    """
    The temperature the water needs so the dough comes out at `dough` °C, with
    a mixer that warms it by `warming` °C.

    `water` is the weight of the water, `others` are the remaining ingredients
    as (weight, heat capacity, temperature). Weights in any unit, as long as it
    is the same for all. None without water.
    """
    if not water:
        return None
    water_capacity = water * WATER_HEAT_CAPACITY
    total_capacity = water_capacity + sum(
        weight * capacity for weight, capacity, _temperature in others
    )
    heat_of_others = sum(
        weight * capacity * temperature for weight, capacity, temperature in others
    )
    return ((dough - warming) * total_capacity - heat_of_others) / water_capacity
