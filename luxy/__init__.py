"""luxy -- a Pythonic client for Yale's LUX API.

Built on top of `luxql <https://github.com/project-lux/luxql>`_ for query
construction and validation. luxql is a hard dependency: every query
luxy builds is a real luxql tree, validated against the LUX
advanced-search-config.

Other features layered on top:

* Pluggable backends (MarkLogic by default, QLever supported).
* Graph-style relationship filters via the ``__`` chain syntax.
* Response profiles (``full`` / ``results`` / ``name`` / ``count``).
* Per-category rate limiting with optional load-aware scaling.
"""

# luxql is required. Re-export its primitives so users can build trees
# directly when they need to.
from luxql import LuxAPI, LuxBoolean, LuxConfig, LuxLeaf, LuxRelationship

from . import complexity
from .api import (
    BaseLux,
    Chain,
    Collections,
    Concepts,
    Events,
    FilterBuilder,
    Objects,
    PeopleGroups,
    Places,
    Works,
    clear_lux_config_cache,
    config,
    get_lux_config,
)
from .backends import (
    Backend,
    MarkLogicBackend,
    QLeverBackend,
    get_default_backend,
    set_default_backend,
    use_local_qlever,
)
from .profiles import (
    PROFILE_COUNT,
    PROFILE_FULL,
    PROFILE_NAME,
    PROFILE_RESULTS,
    VALID_PROFILES,
)
from .rate_limiter import (
    REQUEST_DOCUMENT,
    REQUEST_RELATIONSHIP,
    REQUEST_SIMPLE,
    RateLimiter,
    get_default_rate_limiter,
    make_load_callback,
    set_rate_limits,
)

__version__ = "0.1.0"

__all__ = [
    "Backend",
    "BaseLux",
    "Chain",
    "Collections",
    "Concepts",
    "Events",
    "FilterBuilder",
    "LuxAPI",
    "LuxBoolean",
    "LuxConfig",
    "LuxLeaf",
    "LuxRelationship",
    "MarkLogicBackend",
    "Objects",
    "PROFILE_COUNT",
    "PROFILE_FULL",
    "PROFILE_NAME",
    "PROFILE_RESULTS",
    "PeopleGroups",
    "Places",
    "QLeverBackend",
    "REQUEST_DOCUMENT",
    "REQUEST_RELATIONSHIP",
    "REQUEST_SIMPLE",
    "RateLimiter",
    "VALID_PROFILES",
    "Works",
    "__version__",
    "clear_lux_config_cache",
    "complexity",
    "config",
    "get_default_backend",
    "get_default_rate_limiter",
    "get_lux_config",
    "make_load_callback",
    "set_default_backend",
    "set_rate_limits",
    "use_local_qlever",
]
