# CLAUDE.md

See @README.md for setup, commands, and project structure.

There is no test suite currently.

## Architecture Notes

**Database pattern:** `get_db()` generator in `app/database.py` opens a connection with `row_factory = sqlite3.Row` and closes it unconditionally via `finally`. Injected into routes via `Depends(get_db)`.

**Two tables:**

- `budget_set` — monthly budget allocations: `id, MonthYear (TEXT "MM/YY"), Category, Budget (REAL)`
- `budget_tracker` — transactions: `id, Date, Description, Category, Expenditure (REAL), Year, Month, Day`

**Router ordering:** Static paths (`/export/csv`) are registered **before** parameterised paths (`/{month}/{year}`, `/{id}`) to prevent FastAPI treating "export" as an integer.

**Pydantic models:** Field names use PascalCase to match SQLite column names. `TransactionUpdate` uses all-optional fields; `model_dump(exclude_none=True)` builds the dynamic `SET` clause.

**MonthYear format:** Stored as `"MM/YY"`. Route params `month`/`year` (int) are converted via `f"{month:02d}/{str(year)[-2:]}"` in `budget.py` and `summary.py`.

**MCP:** `.mcp.json` exposes the API as an MCP server via SSE at `http://raspberrypi4.tailad9f80.ts.net:8502/mcp`.
