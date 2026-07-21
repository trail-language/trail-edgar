"""The `edgar.*` field vocabulary this source declares.

Approach X: every source owns its namespace and the language ships no built-in vocabulary. edgar
registers this mapping under the `trail.schema` entry point so `edgar.revenue`, `edgar.total_assets`,
etc. become known, kind-annotated fields once `trail-edgar` is installed. Domain data (income/balance/
cash) is owned by `edgar.*`; the shared `meta.*` coordination fields (sector/country/... - `meta.country`
is the cross-source bridge key) are NOT declared here.
"""
from trail_edgar.mapping import META_FIELDS, PROVIDED_FIELDS, external, kind_of

#: column (dotted, `edgar.*`) -> kind string; consumed by trail's `trail.schema` entry point.
SCHEMA: dict[str, str] = {
    external(f): kind_of(f) for f in sorted(PROVIDED_FIELDS - META_FIELDS)
}
