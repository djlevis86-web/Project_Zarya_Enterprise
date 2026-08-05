# Local demo data seeding

`seed_demo_data` creates deterministic synthetic records for local
visual and workflow testing.

## Safety

The command requires all of the following:

- `ALLOW_DEMO_SEED=1`;
- `DEBUG=True`;
- SQLite;
- non-production settings;
- `BASE_DIR=D:\Project_Zarya`;
- database `D:\Project_Zarya\db.sqlite3`.

The checks are relaxed only for Django's in-memory test database.

## Data ownership

Every generated record is marked with one of these prefixes:

- `[DEMO-ZARYA:<seed>]`;
- `DEMO-ZARYA-`;
- `demo-zarya-`.

`--reset` deletes only these records and their synthetic media files.
Existing users, company requisites, 1C counterparties and real local
documents are not modified.

## Profiles

| Profile | Documents | Current registry | Ready queue | Blocked queue |
|---|---:|---:|---:|---:|
| small | 46 | 12 | 12 | 6 |
| visual | 228 | 78 | 78 | 24 |
| stress | 1290 | 300 | 450 | 180 |

The visual profile mirrors the density required for payment registry,
queue, history, pagination, long names, partial payments and blocked
readiness states.

## Commands

Dry run:

```powershell
$env:ALLOW_DEMO_SEED = "1"
python manage.py seed_demo_data `
    --profile visual `
    --seed 20260805 `
    --dry-run
```

Create:

```powershell
python manage.py seed_demo_data `
    --profile visual `
    --seed 20260805
```

Validate:

```powershell
python manage.py seed_demo_data `
    --profile visual `
    --seed 20260805 `
    --validate-only
```

Replace all prior demo data:

```powershell
python manage.py seed_demo_data `
    --profile visual `
    --seed 20260805 `
    --replace
```

Reset only demo data:

```powershell
python manage.py seed_demo_data --reset
```

## Payment registry workflow acceptance

The visual profile is also intended to verify the registry workflow:

- filter by planned payment date, status, payment state, OCR and search;
- add one ready document without losing the active query;
- add every ready document from the current page in one POST;
- keep the same filter and pagination context after the POST;
- repeat the bulk action page by page for 20–100 documents;
- keep blocked documents in the queue with the repair action.

The bulk action never adds blocked rows. It reuses the canonical
`add_to_payment_registry` service and sends only ready invoice IDs from
the currently rendered page.
