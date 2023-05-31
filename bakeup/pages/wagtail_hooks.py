from wagtail import hooks

@hooks.register("construct_settings_menu")
def hide_user_menu_item(request, menu_items):
    exclude_item_list = ('benutzer', 'gruppen', 'users', 'groups', 'workflows', 'workflow-tasks')
    menu_items[:] = [item for item in menu_items if item.name not in exclude_item_list]


@hooks.register('construct_main_menu')
def hide_snippets_menu_item(request, menu_items):
    exclude_item_list = ('berichte', 'reports')
    menu_items[:] = [item for item in menu_items if item.name not in exclude_item_list]