import functools
from importlib import resources

from .. import queries


@functools.lru_cache()
def load_query(query_name) -> str:
    """Load a predefined GraphQL query and cache it."""
    assert query_name.endswith(".graphql")
    return resources.read_text(queries, query_name)
