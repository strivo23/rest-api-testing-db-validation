# Contributing

Thanks for your interest in this project. It is a portfolio/learning project, but the same
guidelines apply: keep changes small, tested and honest.

## Getting started

```powershell
git clone https://github.com/strivo23/rest-api-testing-db-validation.git
cd rest-api-testing-db-validation

python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Windows
# source .venv/bin/activate         # Linux / macOS

python -m pip install --upgrade pip
pip install -r requirements.txt

copy .env.example .env              # then edit DATABASE_URL
```

The automated unit/API suite runs on in-memory **SQLite** and needs no database server, so you
can start contributing immediately:

```powershell
pytest -v
pytest --cov=app --cov-report=term-missing
```

See the [README](README.md) for PostgreSQL setup, running the server and the Postman collection.

## Project layout

| Path | Responsibility |
| --- | --- |
| `app/routes/` | HTTP layer only - verbs, status codes, query parameters |
| `app/schemas.py` | Pydantic validation and serialisation |
| `app/crud.py` | Data access and business logic (no HTTP errors raised here) |
| `app/models.py`, `app/database.py` | ORM models, engine, sessions |
| `app/errors.py` | Global exception handlers and the error contract |
| `tests/` | pytest suite |

Keep the layer boundaries intact: the routing layer must not contain SQL, and `crud.py` must not
raise HTTP exceptions.

## Guidelines

- **Tests first.** Add or update tests for any behaviour change. A change is not complete until
  `pytest -v` passes.
- **Stay isolated.** Never point the automated suite at a real database. Do not weaken the fixture
  that asserts the tests are bound to SQLite.
- **Validate twice.** New fields need both a Pydantic rule and, where relevant, a database
  constraint.
- **Never commit secrets.** No real `.env` files, credentials or connection strings. Only
  placeholder values belong in `.env.example`.
- **Do not fabricate results.** Test results, coverage figures and validation output in the docs
  must come from actual runs. Mark anything unverified as *pending*.
- **Keep it honest.** If a requested feature is not implemented, document it as a limitation
  instead of claiming it.
- Match the existing style: type hints, descriptive names, and comments only where the logic is
  not self-evident.

## Running the PostgreSQL integration tests

These are opt-in and only run against a database whose name ends with `_test`:

```powershell
$env:TEST_DATABASE_URL="postgresql+psycopg2://postgres:<password>@localhost:5432/defect_tracker_test"
pytest tests/integration -v -m integration
```

## Submitting changes

1. Create a branch: `git checkout -b fix/short-description`
2. Make your change and add tests.
3. Run the full suite and coverage:
   `pytest --cov=app --cov-report=term-missing`
4. Commit with a descriptive message (for example `fix: reject page_size above the documented cap`).
5. Open a pull request describing **what** changed and **how you verified** it.

A GitHub Actions workflow (`.github/workflows/tests.yml`) runs the suite on every push and pull
request.
