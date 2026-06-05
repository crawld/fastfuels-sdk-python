"""
FastFuels SDK.

The top-level namespace re-exports the default API version (currently v1).
Import from a versioned subpackage to pin an API version explicitly:

    from fastfuels_sdk.v1 import Domain   # explicit v1
    from fastfuels_sdk import Domain      # default (v1 until 2.0.0)
"""

from fastfuels_sdk.v1 import *  # noqa: F401,F403
from fastfuels_sdk.v1 import __all__  # noqa: F401
