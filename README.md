# bakeup

Best baking app ever!

[![Built with Cookiecutter Django](https://img.shields.io/badge/built%20with-Cookiecutter%20Django-ff69b4.svg?logo=cookiecutter)](https://github.com/cookiecutter/cookiecutter-django/)
[![Black code style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

License: MIT

## Settings

Moved to [settings](http://cookiecutter-django.readthedocs.io/en/latest/settings.html).

## Basic Commands

### Setting Up Your Users

-   To create a **normal user account**, just go to Sign Up and fill out the form. Once you submit it, you'll see a "Verify Your E-mail Address" page. Go to your console to see a simulated email verification message. Copy the link into your browser. Now the user's email should be verified and ready to go.

-   To create an **superuser account**, use this command:

        $ python manage.py createsuperuser

For convenience, you can keep your normal user logged in on Chrome and your superuser logged in on Firefox (or similar), so that you can see how the site behaves for both kinds of users.

### Setting up tenants

    $ python manage.py migrate_schemas --shared

Create the first primary tenant, schema_name, name and domain should be **localhost**

    $ python manage.py create_tenant

Edit your hosts file (/etc/hosts) and add one for the primary tenanat and for all the other tenants as well

    127.0.0.1       localhost
    127.0.0.1       ole.localhost


### Load fixtures

    $ python manage.py tenant_command loaddata --schema=schema_name bakeup/users/fixtures/demo-data.json
    $ python manage.py tenant_command loaddata --schema=schema_name bakeup/shop/fixtures/demo_customers.json
    $ python manage.py tenant_command loaddata --schema=schema_name bakeup/workshop/fixtures/categories.json
    $ python manage.py tenant_command loaddata --schema=schema_name bakeup/workshop/fixtures/demo-products.json
    $ python manage.py tenant_command loaddata --schema=schema_name bakeup/shop/fixtures/demo_baking_days.json

### Type checks

Running type checks with mypy:

    $ mypy bakeup

### Test coverage

To run the tests, check your test coverage, and generate an HTML coverage report:

    $ coverage run -m pytest
    $ coverage html
    $ open htmlcov/index.html

#### Running tests with pytest

    $ pytest

### Live reloading and Sass CSS compilation

Moved to [Live reloading and SASS compilation](http://cookiecutter-django.readthedocs.io/en/latest/live-reloading-and-sass-compilation.html).

### Sentry

Sentry is an error logging aggregator service. You can sign up for a free account at <https://sentry.io/signup/?code=cookiecutter> or download and host it yourself.
The system is set up with reasonable defaults, including 404 logging and integration with the WSGI application.

You must set the DSN url in production.

## Deployment

The following details how to deploy this application.
