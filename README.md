![Lux Logo](https://github.com/project-lux/luxy/blob/main/docs/images/luxy-logo.jpg?raw=true)

[![PyPI version](https://badge.fury.io/py/luxy.svg)](https://badge.fury.io/py/luxy)
[![GitHub stars](https://img.shields.io/github/stars/project-lux/luxy.svg)](https://github.com/project-lux/luxy/stargazers)
[![GitHub release](https://img.shields.io/github/v/release/project-lux/luxy)](https://github.com/project-lux/luxy/releases)


LuxY is a Python wrapper for Yale's [Lux API](https://lux.collections.yale.edu/). Lux allows users to search and filter the collections of Yale's museums and libraries, as well as external collections. This lets you find and connect with the cultural heritage collections across Yale's museums, archives, and libraries in new ways and all in one place.

LuxY gives you a Pythonic way to interact with the Lux API: filtering, paginating, downloading data as JSON, and walking the relationship graph between people, works, places and concepts.

## What's new in 0.1.0

- **Built on [`luxql`](https://github.com/project-lux/luxql).** Every query luxy builds is a real luxql tree, validated against the LUX advanced-search-config. There is no parallel dict / DSL: the luxql tree is the query.
- **Graph-style `filter()`.** Walk the LUX graph in one expression with the `__` chain syntax (`produced__classification__name="painting"`).
- **Pluggable backends.** Default is the public LUX `MarkLogicBackend`; a `QLeverBackend` is included for testing against a local QLever + lmdb instance.
- **Response profiles.** Ask for `full`, `results`, `name`, or `count` to avoid pulling whole documents when a label is enough.
- **Adaptive rate limiting.** Documents are unlimited, simple searches default to `1/s`, relationship searches to `1/3s`. Plug in a load endpoint to scale the limits dynamically.
- **Query complexity.** Inspect `q.query_complexity()` (computed from the luxql tree) to choose your batching strategy.

# Installation

```bash
pip install luxy
```

LuxY **requires** `luxql` for query construction. The `pip install` above pulls it in transitively. If you need to install it manually:

```bash
pip install "luxql @ git+https://github.com/project-lux/luxql.git@main"
```

Optional extras:

```bash
pip install "luxy[lmdb]"      # local lmdb cache for QLeverBackend
pip install "luxy[qlever]"    # SPARQLWrapper for talking to QLever
pip install "luxy[all]"
```

# Usage

The classes of LuxY replicate the classes of the Lux API:

1. `PeopleGroups` (`agent`) -- People and Groups, individuals or organizations
2. `Objects` (`item`) -- Physical objects in Yale's collections
3. `Works` (`work`) -- Visual and textual works
4. `Places` (`place`) -- Geographic locations
5. `Concepts` (`concept`) -- Types, materials, languages, currencies, ...
6. `Events` (`event`) -- Historical events
7. `Collections` (`set`) -- Curated collections

## Understanding options

```python
from luxy import PeopleGroups

PeopleGroups().list_filters()
options = PeopleGroups().get_options()
```

## Basic searches

```python
from luxy import PeopleGroups, Objects, Works, Places, Concepts, Events, Collections

PeopleGroups().filter(name="Rembrandt").get()
Objects().filter(name="Rembrandt").get()
Works().filter(name="Painting").get()
Places().filter(name="Amsterdam").get()
Concepts().filter(name="gilding").get()
Events().filter(name="Thirty Years War").get()
Collections().filter(name="Letters").get()
```

Every `.get()` returns the same instance enriched with `url`, `view_url`, `json`, `num_results`, `complexity` and `rate_limit_category`.

## Numerical and date filters

LuxY accepts both the legacy tuple form and Django-style comparator aliases (`gt`, `gte`, `lt`, `lte`, `eq`, `ne`):

```python
Objects().filter(height=(1, ">=")).get()
Objects().filter(height__gte=1).get()
Objects().filter(encounteredDate=("1987-01-01T00:00:00.000Z", ">=")).get()
Objects().filter(encounteredDate__gte="1987-01-01T00:00:00.000Z").get()
```

## Graph-style relationship queries

Use `__` to walk relationships in a single expression:

```python
# People who created paintings
PeopleGroups().filter(produced__classification__name="painting").get()

# Objects whose creator was born in Amsterdam
Objects().filter(producedBy__startAt__name="Amsterdam").get()
```

You can still nest dicts the old-fashioned way and the result is identical:

```python
PeopleGroups().filter(gender={"name": "male"}).get()
PeopleGroups().filter(produced={"classification": {"name": "painting"}}).get()
```

## Boolean groups

```python
from luxy import Objects

result = (
    Objects()
    .filter(hasDigitalImage=True)
    .filter(
        OR=[
            Objects().memberOf("Letters", depth=2),
            Objects().memberOf("Letters", depth=3),
            Objects().memberOf("Letters", depth=4),
        ]
    )
    .filter(name="letter")
    .get()
)
```

## Response profiles

Profiles let you avoid pulling whole documents when you only need a label or a count. They apply to `.get()` and to per-page fetches.

```python
from luxy import PeopleGroups, PROFILE_NAME, PROFILE_COUNT

# Just labels:
slim = PeopleGroups().filter(name="Rembrandt").get(profile=PROFILE_NAME)
for item in slim.json["orderedItems"]:
    print(item["label"], item["id"])

# Just the total count:
count = PeopleGroups().filter(name="Rembrandt").get(profile=PROFILE_COUNT).json["totalItems"]
```

Available profiles: `PROFILE_FULL` (default), `PROFILE_RESULTS`, `PROFILE_NAME`, `PROFILE_COUNT`.

## Backends: MarkLogic and QLever

By default, luxy talks to the public LUX MarkLogic API. To switch to a local QLever (with optional lmdb-backed result cache) and fall back to MarkLogic when QLever can't translate a query:

```python
from luxy import use_local_qlever

use_local_qlever(endpoint="http://localhost:7019", lmdb_path="/var/cache/luxy")
# Equivalent to:
#   QLeverBackend(endpoint=..., lmdb_path=..., fallback=MarkLogicBackend())
#   then set_default_backend(...)
```

Or build the backend manually:

```python
from luxy import MarkLogicBackend, QLeverBackend, set_default_backend

qlever = QLeverBackend(
    endpoint="http://localhost:7019",
    lmdb_path="/var/cache/luxy",
    fallback=MarkLogicBackend(),
)
set_default_backend(qlever)
```

You can also pass a backend per query:

```python
from luxy import Objects, MarkLogicBackend

backend = MarkLogicBackend(base_url="https://staging.example.org/api")
Objects(backend=backend).filter(name="x").get()
```

## Rate limiting

Different LUX requests have very different costs, so luxy splits them into three buckets:

| Bucket          | Default minimum interval | When it applies                                  |
|-----------------|--------------------------|--------------------------------------------------|
| `document`      | unlimited                | `get_item_data` and other single-document fetches |
| `simple`        | 1/second                 | Searches with no relationship hops                |
| `relationship` | 1/3 seconds              | Searches that walk the graph                      |

`luxy` picks the bucket automatically by computing the query complexity from the luxql tree.

```python
from luxy import set_rate_limits

set_rate_limits(simple=0.5, relationship=2.0)   # tighter intervals
set_rate_limits(document=None, simple=1, relationship=3)  # restore defaults
```

If LUX exposes (or one day exposes) a load endpoint, plug it in:

```python
from luxy import RateLimiter, make_load_callback

limiter = RateLimiter(
    load_callback=make_load_callback("https://lux.collections.yale.edu/api/load"),
)
limiter.set_interval("simple", 1.0)
Objects().with_rate_limiter(limiter).filter(name="x").get()
```

The interval used for the next request is `base * load_factor`, so a load factor of `1.5` makes a 1-second interval into 1.5 seconds.

## Query complexity

```python
q = PeopleGroups().filter(produced__classification__name="painting")
q.query_complexity()           # numeric score, walked over the luxql tree
q._category_for_query()        # 'simple' or 'relationship'
q.to_dict()                    # JSON view of the luxql tree
q.to_luxql()                   # the LuxAPI tree itself
```

## Working directly with luxql

When you need full control, ask for the luxql tree and build with it directly:

```python
from luxy import PeopleGroups, LuxBoolean, LuxLeaf, LuxRelationship

q = PeopleGroups()
api = q.to_luxql()             # LuxAPI("agent")

# Add another condition straight to the luxql tree
LuxLeaf("hasDigitalImage", value=True, parent=api.children[0])
print(api.to_json())
```

Anything you can express in luxql you can hand to luxy via the same tree. luxy's
`filter()` is just a convenience layer over the same primitives.

## Pagination

```python
from luxy import PeopleGroups

result = PeopleGroups().filter(endAt={"name": "Amsterdam"}).get()

print("Number of results:", result.num_results)
print("Number of pages:", result.num_pages())

for i, page in enumerate(result.get_page_data_all(), 1):
    if i > 2:
        break
    print(f"Page {i}:", page["id"])
    for item in result.get_items(page):
        print("  ", result.get_item_data(item)["_label"])
```

The page fetcher honours the same rate limit as the original search; `get_item_data` uses the unlimited `document` bucket.

# Roadmap

- [x] luxql-backed query construction
- [x] Graph-style `__` filter chains
- [x] Pluggable backends (MarkLogic, QLever)
- [x] Response profiles (`full`, `results`, `name`, `count`)
- [x] Per-category rate limiting + load-aware scaling
- [x] Query complexity calculation
- [ ] Full SPARQL translation in `QLeverBackend` (currently leaf/AND only)
- [ ] Streaming downloader for very large result sets
