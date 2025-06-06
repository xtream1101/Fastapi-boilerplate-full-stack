# Vars
db_name := "fastapi-boilerplate-db"
project_dir := justfile_dir()

using_infisical := path_exists(project_dir + "/.infisical.json")
infisical_command := if using_infisical == "true" { "infisical run --env=dev --path=/app -- " } else { "" }

# Start all Servers
start:
    @echo "Starting all servers"
    just --justfile {{ justfile() }} db-start
    just --justfile {{ justfile() }} server-start

# Run fast api dev server
server-start:
    just --justfile {{ justfile() }} build-styles
    @cd "{{ project_dir }}"; {{ infisical_command }} uv run alembic upgrade head
    @cd "{{ project_dir }}"; {{ infisical_command }} uv run fastapi dev app/app.py

# Clear db and start all services
fresh-start:
    @echo "Clearing database and starting all servers"
    just --justfile {{ justfile() }} db-stop
    just --justfile {{ justfile() }} start

# Start the postgres db
db-start:
    @echo "Starting database"
    # TODO: Better way to check if the container is already running
    docker run --name {{ db_name }} -e POSTGRES_PASSWORD=postgres -d -p 5432:5432 postgres || true

# Stop the postgres db
db-stop:
    @echo "Stopping database"
    docker stop {{ db_name }} || true
    docker rm {{ db_name }} || true

# Npm watch styles
watch-styles:
    @cd "{{ project_dir }}"; {{ infisical_command }} npm run watch-styles

# Npm build styles
build-styles:
    @cd "{{ project_dir }}"; {{ infisical_command }} npm run build-styles
