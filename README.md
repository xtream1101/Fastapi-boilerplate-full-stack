# Boilerplate using Fastapi and Server Side Rendering


## 🛠️ Stack

- [Fastapi](https://fastapi.tiangolo.com/)
- [Jinja2](https://jinja.palletsprojects.com/en/stable/) for templates
- [Tailwindcss](https://tailwindcss.com/) for styling
- [fastapi-sso](https://github.com/tomasvotava/fastapi-sso) for SSO support
- [Alembic](https://alembic.sqlalchemy.org/en/latest/) for database migrations
- [SQLAlchemy](https://www.sqlalchemy.org/) for ORM

---


## 📦 Features

- Optional SSO/OIDC logins
- Optional verify user by email as well as welcome emails (must have smtp server configured)
- Option to disable registration
    - if disabled, admins can manually invite users

---


## 📝 Upcoming features

- Add mkdocs server
- Add api examples


---


## 🚀 Quick Start Guide


### 🐳 Docker

1. Install [Docker](https://www.docker.com/)
2. Copy the `.env.example` file to `.env`. All default will work to test, but you can change the values if you want.
3. Run the following command:

    ```bash
    docker compose up
    ```


### 🚀 Local Development

1. Install the following tools:
    - [pre-commit](https://pre-commit.com/)
    - [uv](https://github.com/astral-sh/uv)
    - [justfile](https://github.com/casey/just) _(optional)_
    - [docker](https://www.docker.com/) _(optional)_
2. Clone the repository
3. Run the following commands:

    ```bash
    # Setup pre-commit hooks
    pre-commit install
    ```

    ```bash
    # Setup the python environment
    uv sync
    ```

    ```bash
    # Needed to build the tailwind styles
    npm install
    just build-styles
    ```

    ```bash
    # Run the server
    just start
    ```

4. Visit `http://localhost:8000` in your browser
5. Check the other `just` commands available in the `justfile`
    - `just --list`


## 📜 License

This project is licensed under the [...](LICENSE).
