# Boilerplate using Fastapi and Server Side Rendering


## Stack

- Fastapi
- Jinja2 for templates
- Tailwindcss for styling
- fastapi-sso for SSO support
- alembic for database migrations
- SQLAlchemy for ORM


## Features

- Optional SSO/OIDC logins
- Optional verify user by email as well as welcome emails (must have smtp server configured)
- Option to disable registration
    - if disabled, admins can manually invite users


## TODO's

- Better admin interface
- Add docs server using mkdocs
- Add precommit hooks
- Add dockerfile/docker-compose samples
- Create a better light/dark theme
