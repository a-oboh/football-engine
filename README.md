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
API_FOOTBALL_KEY=your_api_football_v3_key_here
API_FOOTBALL_BASE_URL=https://v3.football.api-sports.io
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
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

To ingest several seasons for the same competition, place the CSV files in one
directory. Each filename must include its season, for example
`epl_2023_24.csv`, `epl_2024_25.csv`, and `epl_2025_26.csv`.

### Bulk filename convention

`bulk-ingest` assigns every CSV in the selected directory to the competition
given on the command line. It derives only the season from the filename.

| Filename | Stored season |
| --- | --- |
| `epl_2023_24.csv` | `2023-24` |
| `epl-2024-25.csv` | `2024-25` |
| `epl_2025_2026.csv` | `2025-26` |

Use a four-digit start year followed by `-` or `_`, then either a two- or
four-digit end year. CSV files without one of these season tokens, such as
`latest.csv`, are rejected rather than assigned an uncertain season. Put only
the season CSVs you intend to ingest directly in the selected directory.

```bash
uv run football-analytics bulk-ingest path/to/epl-seasons \
  --competition-name "Premier League" \
  --competition-code EPL
```

The bulk operation is atomic: if any CSV fails validation or its filename does
not contain a season token, no files from that directory are committed.

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

The command prints expected goals, the most likely score fields (`FTHG`,
`FTAG`, `HTHG`, and `HTAG`), and core markets: 1X2, Over/Under 2.5 goals, and
Both Teams To Score. Each market includes its model probability and `fair_odds`
(decimal odds calculated as `1 / probability`). Fair odds deliberately exclude
any bookmaker margin and are a model benchmark, not a bookmaker quote.

Half-time expected goals are calibrated using the selected seasons' observed
share of goals scored before half-time. The command uses only completed matches
in the selected seasons; the requested fixture is never recorded in the
database before it is predicted.

## Live Data Ingestion (`api-football.com` v3)

Once `API_FOOTBALL_KEY` is configured in `.env`, you can sync completed fixtures (`FT`), upcoming scheduled fixtures (`NS`/`TBD`), match statistics, and pre-match bookmaker odds directly from `api-football.com`:

```bash
# Sync fixtures, match statistics, and pre-match bookmaker odds
uv run football-analytics sync-fixtures \
  --competition-code E0 \
  --season 2024-2025 \
  --include-stats \
  --include-odds
```

Team names from `api-football.com` are automatically reconciled with historical CSV names via the `team_aliases` table so sequential Poisson histories remain unbroken across data sources.

## FastAPI `/api/v1` Server & Football Engine Lab UI

Start the FastAPI backend server:

```bash
uv run football-analytics serve --host 127.0.0.1 --port 8000 --reload
```

- **Interactive Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc API Reference**: `http://127.0.0.1:8000/redoc`
- **Raw OpenAPI 3.1 Schema**: `http://127.0.0.1:8000/openapi.json`
- **Core Endpoints**:
  - `GET /api/v1/health` — Database & `api-football.com` configuration status
  - `GET /api/v1/overview` — Corpus summary, competition coverage, and recent matches
  - `GET /api/v1/competitions` & `GET /api/v1/teams` — Competitions, seasons, and teams
  - `GET /api/v1/models` — Active model metadata, parameters, and assumptions
  - `GET /api/v1/matches` & `GET /api/v1/matches/{id}` — Paginated historical match explorer with statistics & bookmaker odds
  - `GET /api/v1/fixtures/upcoming` — Upcoming scheduled fixtures and pre-match odds
  - `POST /api/v1/predictions` & `GET /api/v1/predictions/{slug}` — Run or retrieve reproducible match predictions (`hypothetical`, `historical` walk-forward cutoff, or `upcoming` modes)
  - `POST /api/v1/evaluations` & `GET /api/v1/evaluations/{slug}` — Run or retrieve walk-forward backtests with calibration curves and bookmaker comparisons
  - `POST /api/v1/sync/api-football` & `GET /api/v1/sync/status` — Trigger live `api-football.com` ingestion and inspect sync logs

The companion React frontend lives in the sibling directory [`../football-web`](../football-web).

