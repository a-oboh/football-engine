# Football Analytics

This is a personal experiment to analyze football data.

## Setup

### 1. Install prerequisites

Install:

- Python 3.14 or newer
- PostgreSQL
- uv

On macOS with Homebrew:

```bash
brew install postgresql@16 uv
brew services start postgresql@16
```

### 2. Install project dependencies

From the project root:

```bash
uv sync
```

### 3. Create the PostgreSQL database

Open `psql` as your local PostgreSQL admin user:

```bash
psql postgres
```

Create a dedicated app user and database:

```sql
CREATE USER football_analytics_user WITH PASSWORD 'football_analytics_password';
CREATE DATABASE football_analytics OWNER football_analytics_user;
GRANT ALL PRIVILEGES ON DATABASE football_analytics TO football_analytics_user;
\q
```

If you prefer to use your current macOS/Linux user instead of creating a dedicated
Postgres user, this is also fine:

```bash
createdb football_analytics
```

### 4. Configure environment variables

Create a local `.env` file:

```bash
cp .env.example .env
```

Set `DATABASE_URL` in `.env`.

If you created the dedicated user above:

```env
DATABASE_URL=postgresql+psycopg://football_analytics_user:football_analytics_password@localhost:5432/football_analytics
```

If you created the database with your current system user:

```env
DATABASE_URL=postgresql+psycopg://localhost:5432/football_analytics
```

### 5. Run database migrations

Alembic reads `DATABASE_URL` from `.env`, so run migrations from the project root:

```bash
uv run alembic upgrade head
```

Check the current migration version:

```bash
uv run alembic current
```

See migration history:

```bash
uv run alembic history
```

Create a new migration after changing SQLAlchemy models:

```bash
uv run alembic revision --autogenerate -m "describe your change"
uv run alembic upgrade head
```

### 6. Verify the setup

Confirm the database responds:

```bash
psql "postgresql://football_analytics_user:football_analytics_password@localhost:5432/football_analytics" -c "SELECT 1;"
```

Or, if you are using your current system user:

```bash
psql football_analytics -c "SELECT 1;"
```

Run the test suite:

```bash
uv run pytest
```

Run the app entry point:

```bash
uv run football-analytics
```

You can also run the module directly:

```bash
uv run python -m football_analytics
```
