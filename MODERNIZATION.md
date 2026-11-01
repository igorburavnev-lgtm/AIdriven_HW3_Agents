# MODERNIZATION.md

I started by trying to run the project exactly as it was handed over, because I didn't want to
guess which parts were broken. `python manage.py check` failed immediately:

```
django.core.exceptions.ImproperlyConfigured: Error loading psycopg2 or psycopg module
```

That told me the settings file hard-codes PostgreSQL and the driver isn't part of my environment,
so nothing else could even be evaluated. I changed the database configuration first, re-ran the
check, and got the next failure:

```
File "dashboard/services/graph.py", line 5, in <module>
    from tinkoff.invest import CandleInterval, Client
ModuleNotFoundError: No module named 'tinkoff'
```

Two blockers, both confirmed by actually running the code rather than by reading it. The rest of
this document is what I changed and why.

---

## 1. Dependencies

### 1.1 What I was working with

The original `requirements.txt` pinned 40 packages — every direct *and* transitive dependency,
including build tools (`black`, `isort`, `mypy-extensions`, `pathspec`, `platformdirs`, `tomli`).
That makes a single security upgrade almost impossible, because you have to re-derive the whole
graph by hand.

My rule for the rewrite: pin **direct** dependencies only, let the resolver handle transitives, and
target Python 3.11+.

### 1.2 Package table

| Package | Before | After | Why update | What would break without it | How I verified |
|---|---|---|---|---|---|
| Django | 4.1.7 | **5.2.18** | 4.1 has had no security fixes since December 2023. 5.2 is the LTS line (supported to April 2028). | Old line: known CVEs stay unfixed. New line: nothing — this is the target. | `django.get_version()` → 5.2.18; `check`, `migrate`, 33 tests |
| djangorestframework | 3.14.0 | **3.16.1** | 3.14 uses APIs removed in Django 5 (`NullBooleanField`, old timezone helpers). | DRF imports fail at start-up on Django 5.2. | all 25 API tests pass |
| django-filter | 22.1 | **25.2** | 22.1 (2022) is not compatible with Django 5.x. | `/api/v1/shares/?ticker=…` raises on import. | filter tests + `check` |
| django-crispy-forms | 2.0 | **2.4** | 2.x changed the template-pack mechanism; 2.0 misbehaves on Django 5.2. | create/update forms render without Bootstrap markup. | manual `GET /create` + `GET /login` |
| crispy-bootstrap3 | 2022.1 | **2024.1** | Must match crispy 2.x. | `{% crispy %}` raises TemplateDoesNotExist. | `check` + form pages |
| celery | 5.2.7 | **5.5.3** | 5.2 does not support Python 3.12 and conflicts with kombu 5.6. | worker/beat fail to start on 3.11+. | `check` imports `config.celery` successfully |
| redis (client) | 4.5.1 | **6.4.0** | 4.x is broken on 3.12 (removed `distutils` in its build chain). | broker connection code fails to import. | `redis.__version__` → 6.4.0 |
| psycopg2-binary | 2.9.5 | **psycopg[binary] 3.3.6** | `psycopg2-binary` is explicitly not recommended for production; psycopg 3 is the modern driver and Django 5.2 supports it natively. | On a machine without libpq bindings, `migrate` dies (this is exactly the error I hit first). | settings switch to SQLite by default; PostgreSQL path uses the new driver |
| plotly | 5.13.1 | **6.9.0** | 5.13 pins an old `tenacity`; 6.x is current. | no failure, but drags an outdated dependency tree. | `plotly.offline.plot` exists and produces the div; unit tests on the helpers |
| tinkoff | 0.1.1 | **removed** | Duplicated the `tinkoff` namespace with `tinkoff-investments`; whichever installed last won. Deleted from PyPI anyway. | Unpredictable imports, then an uninstallable requirement. | PyPI returns 404 for `/simple/tinkoff/` |
| tinkoff-investments | 0.2.0b50 | **moved to `requirements-tinkoff.txt`** | Deleted from PyPI; upstream repo archived. | `pip install -r requirements.txt` cannot resolve it. | PyPI 404 + GitHub API `"archived": true` |
| pytz | 2022.7.1 | **removed** | Django 4+ and Python 3.9+ use `zoneinfo`; nothing imports pytz. | nothing | `grep pytz` → no imports |
| six, cachetools, tenacity, grpcio, protobuf, pydantic, async-timeout, … | various | **removed** | All transitive; they come back automatically if something needs them. | nothing | clean install + imports |

### 1.3 The Tinkoff SDK problem

This is the most consequential finding, so I checked it twice before acting:

```
https://pypi.org/simple/tinkoff-investments/  -> 404
https://pypi.org/pypi/tinkoff/json            -> 404
https://pypi.org/simple/django/               -> 200   (sanity check: the index works)
https://api.github.com/repos/RussianInvestments/invest-python -> "archived": true, pushed 2025-10-09
```

So the vendor SDK is neither installable nor maintained. Pinning it in `requirements.txt` would make
the file unusable, which is why I:

1. removed it from the runtime requirements;
2. put it into an optional `requirements-tinkoff.txt` pointing at the archived repository;
3. made every import of it **lazy**, inside the function that needs it.

Point 3 matters: because of it the web app, the REST API and the whole test suite run without the
package, and only live market-data calls require it.

### 1.4 Resulting files

`requirements.txt` (9 pinned runtime packages), `requirements-dev.txt` (black/isort/coverage),
`requirements-tinkoff.txt` (optional SDK).

---

## 2. Configuration fixes

All settings changes are in `config/settings.py`. I moved the machine-specific values into the
environment and kept development defaults so that a fresh clone runs with no setup.

| Setting | Before | After | Why |
|---|---|---|---|
| `SECRET_KEY` | `""` | `DJANGO_SECRET_KEY`, dev fallback, **raises** if the fallback is used with `DEBUG=False` | an empty key cannot sign sessions or CSRF tokens |
| `DEBUG` | `True` hard-coded | `DJANGO_DEBUG` (default `true`) | one file can't be both dev and prod |
| `ALLOWED_HOSTS` | `[]` | `localhost`, `127.0.0.1`, `[::1]`, `testserver` + `DJANGO_ALLOWED_HOSTS` | with `[]` the site only answered requests addressed to localhost |
| `DATABASES` | hard-coded PostgreSQL | SQLite by default; PostgreSQL when `DB_ENGINE=postgres` / `POSTGRES_DB` is set; credentials from env | this was blocker #1 |
| `TINKOFF_TOKEN` | `""` in source | `TINKOFF_TOKEN` env var | secret in VCS |
| `CELERY_BROKER_URL` | hard-coded constant | `CELERY_BROKER_URL` env var, same default | staging/prod need different brokers |
| `STATIC_URL` | `"static/"` | `"/static/"` + `STATIC_ROOT` | relative URL broke CSS on `/update/12` and `/user/login/` |
| LOGGING file | `"app.logs"` (relative to CWD) | `BASE_DIR / "app.logs"`, UTF-8 | logs vanished depending on where you started the process |

I also added `LOGIN_URL`, `LOGIN_REDIRECT_URL`, `LOGOUT_REDIRECT_URL` so that Django's own
redirects behave predictably.

### 2.1 Celery schedule

The original beat schedule was:

```python
app.conf.beat_schedule = {"add-every-5-min": {"task": "...update_last_price", "schedule": 10.0}}
```

The key says five minutes, the value says ten seconds, and the task name says "add" while the task
updates. I couldn't recover which number was intended, so I made it explicit and configurable:
key `update-last-price`, interval from `PRICE_UPDATE_INTERVAL_SECONDS`, default **300 s** (the value
the key name claims). Ten seconds against a catalogue of hundreds of instruments would also have
tripped the broker's rate limits almost immediately.

`docker-compose.yml` got the same treatment: `./:/app` used to mount the project over the PostgreSQL
data directory, so the cluster was recreated (or failed to initialise) on every start. It is now a
named volume, with pinned images and a healthcheck.

---

## 3. Startup fixes

| # | Problem | Fix | File |
|---|---|---|---|
| 1 | Hard-coded PostgreSQL, no driver | env-driven DB, SQLite default | `config/settings.py:141-163` |
| 2 | `from tinkoff.invest import …` at module level | deferred import inside the function | `dashboard/services/market_data.py:27`, `dashboard/services/graph.py:17`, `dashboard/management/commands/add_shares.py:12` |
| 3 | Empty `SECRET_KEY` | env var with dev fallback + prod guard | `config/settings.py:36`, `:47-50` |
| 4 | `ALLOWED_HOSTS = []` | sensible defaults | `config/settings.py:40-43` |
| 5 | `STATIC_URL` without leading slash | `"/static/"` | `config/settings.py:189-190` |
| 6 | CWD-dependent log file | `BASE_DIR / "app.logs"` | `config/settings.py:88-93` |
| 7 | Hard-coded broker | env var | `config/settings.py:207` |

Migrations needed no repair: `makemigrations --check` reported `No changes detected` once the app
could start, so the seven existing migrations are consistent with `models.py`.

---

## 4. Defect fixes

These were not blocking start-up, but they broke behaviour badly enough to be worth fixing in the
same pass. I kept each one small and verifiable.

Short module names in the table below are relative: `graph.py` and `market_data.py` live in
`dashboard/services/`, `add_shares.py` in `dashboard/management/commands/`, `detail.html` and
`list.html` in `dashboard/templates/dashboard/`.

| Defect | What was wrong | Fix |
|---|---|---|
| Detail page 500 | `Share.objects.get(id=pk)` raised `DoesNotExist` for an unknown id | `get_object_or_404` (`dashboard/views.py:37`) |
| Detail page 500 on API outage | no error handling around the Tinkoff call | `try/except` + message rendered instead of a graph (`dashboard/views.py:39-47`, `detail.html`) |
| Login page had no inputs | the **class** `AuthForm` was passed to the template, so `{{ form.email }}` resolved to a field object | pass instances (`user/views.py:25, 54`) |
| Login crash | `post` read `form.data[...]` without validating | `form.is_valid()` + `cleaned_data` (`user/views.py:31-37`) |
| Registration crash | `form.errors["__all__"]` → `KeyError` for field-level errors | safe first-error helper (`user/views.py:10-14, 76`) |
| Registration crash | `self.cleaned_data["email"]` → `KeyError` when the e-mail was invalid | `.get()` (`user/forms.py:41`) |
| Nobody could log in with a mixed-case e-mail | registration stored the address as typed, login lowercased it | normalise on registration + `email__iexact` check (`user/forms.py:41, 49`) |
| Password policy ignored | plain `forms.Form` bypassed `AUTH_PASSWORD_VALIDATORS` | explicit `validate_password()` (`user/forms.py:54`) |
| Prices lost their kopecks | only `Quotation.units` was read, `nano` ignored (100.55 → 100) | `quotation_to_float()` (`dashboard/services/market_data.py:10-17`) |
| Same in the chart | `candle.close.units` | `quotation_to_float(candle.close)` (`graph.py:28`) |
| `updated_at` never changed | `QuerySet.update()` bypasses `auto_now` | `save(update_fields=[…, "updated_at"])` (`dashboard/tasks.py:29`) |
| First price write logged an error every run | comparison with `None` raised `TypeError`, caught to mean "growth" | explicit `if share.last_price is None` (`dashboard/tasks.py:17-20`) |
| `add_shares` aborted on renamed instruments | `get_or_create` matched on **all** fields → duplicate `figi` → IntegrityError | match on `figi`, pass `defaults` (`add_shares.py:23-32`) |
| `IndexError` on empty price list | `last_prices.pop()` | explicit check + clear `ValueError` (`market_data.py:32-33`) |
| Chart legend said "test" | hard-coded `name="test"` | `name=share.ticker` (`graph.py:36`) |
| Every response embedded ~3 MB of plotly.js | `include_plotlyjs` defaulted to `True` while the page already loads it from a CDN | `include_plotlyjs=False` (`graph.py:46`) |
| Broken grid in the detail template | Bootstrap class `col3` instead of `col-3` | `col-3` (`detail.html:9-31`) |
| Indicator couldn't distinguish "falling" from "no data" | `{% if %}` treated `None` as falling | three-state cell (`list.html:35-41`) |
| Wildcard import | `from .views import *` | explicit imports (`api/v1/router.py:3-4`) |
| Logout only via GET | state change without CSRF | kept GET for compatibility, added `post` alias (`user/views.py:88`) |

I deliberately did **not** touch two things:

- the share API remains `AllowAny` (changing it would break the documented contract and its tests);
- `uid` is still absent from `ShareSerializer`, so a second API-created share can still hit the
  UNIQUE constraint. Fixing it means changing the API schema, which belongs to a separate change.

---

## 5. Refactoring

I only refactored where it made the code obviously better without changing behaviour:

| Change | Where | Why |
|---|---|---|
| `env_bool` / `env_list` helpers | `config/settings.py:10-27` | seven `os.environ.get(...)` calls with inline parsing would be noise |
| `settings.TINKOFF_TOKEN` instead of `from config.settings import TINKOFF_TOKEN` | services, command | one direction of dependency; also makes `override_settings` work in tests |
| `quotation_to_float` extracted | `market_data.py:10-17` | the conversion was duplicated in two modules and wrong in both |
| `_form_error_message` helper | `user/views.py:10-14` | two views needed the same "first error of any field" walk |
| Flattened the nested `try/except` in the task | `dashboard/tasks.py` | the inner block existed only to catch a `TypeError` the code itself created |
| Explicit router imports | `api/v1/router.py` | wildcard imports hide dependencies |

---

## 6. Verification

Every step below was actually executed. Environment: CPython 3.12.14, Windows, SQLite.

| Check | Command | Result |
|---|---|---|
| System checks | `python manage.py check` | `System check identified no issues (0 silenced).` |
| Migration drift | `python manage.py makemigrations --check --dry-run` | `No changes detected` |
| Migrations | `python manage.py migrate` | 7 original + 1 new `dashboard` migration applied |
| Server | `python manage.py runserver 127.0.0.1:8124 --noreload` | started, probed, stopped |
| — `GET /` | | `200`, 2751 bytes |
| — `GET /api/v1/shares/` | | `200` |
| — `GET /user/login/` | | `200`, contains `name="email"` and `type="password"` |
| — `GET /admin/` | | `200` |
| Tests | `python manage.py test dashboard` | **33 tests, OK** (10 original + 4 regression + 19 portfolio) |

A note on installing dependencies: `pip install` is blocked in this sandbox — it cannot create its
unpack directory (even for a trivial pure-Python wheel). I installed the same PyPI wheels by
extracting them into the venv. The versions match `requirements.txt` exactly and were confirmed by
importing and printing them (Django 5.2.18, DRF 3.16.1, celery 5.5.3, redis 6.4.0, plotly 6.9.0).

---

## 7. What is still not right

1. **Tinkoff SDK is unavailable from PyPI.** Only the degraded paths are verified here: the detail
   page without a graph, and the price task with no quotes. Live API calls need
   `requirements-tinkoff.txt` and a token.
2. **Redis was never running.** The Celery configuration is verified statically and by tests only.
3. **PostgreSQL was not exercised.** The switch exists (`DB_ENGINE=postgres`), migrations contain no
   raw SQL, but I could not run them against a real server here. Related: `search_fields = ["$name"]`
   in the share API uses PostgreSQL regex search and will error on SQLite if `?search=` is used.
4. **`uid` / API share creation** still has the latent UNIQUE conflict described above.
5. **Front-end assets come from CDNs.** Without internet the page loses its styling and the chart
   library; only the Bootstrap CSS is vendored locally.
