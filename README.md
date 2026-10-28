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

## Ingest completed results and predict a fixture

Ingest a CSV containing completed matches. At minimum it must contain `Date`,
`HomeTeam`, `AwayTeam`, `FTHG`, `FTAG`, and `FTR`. Optional statistics and odds
columns are stored when present.

```bash
uv run football-analytics ingest path/to/epl_2025_26.csv \
  --competition-name "Premier League" \
  --competition-code EPL \
  --season 2025-26
```

Run this again after new matches are completed; matches already stored for the
same season, teams, and date are skipped. Rows for unplayed fixtures with blank
final scores are ignored. Use explicit season names for every file, especially
for an in-progress season.

After ingesting historical seasons and the completed matches from the current
season, predict an upcoming fixture:

```bash
uv run football-analytics predict \
  --competition-code EPL \
  --season 2023-24 \
  --season 2024-25 \
  --season 2025-26 \
  --home-team "Arsenal" \
  --away-team "Chelsea"
```

The command prints expected goals and H/D/A probabilities. It uses only the
completed matches in the selected seasons; the requested fixture is never
recorded in the database before it is predicted.
