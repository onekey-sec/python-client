import functools

try:
    from importlib import resources
except ImportError:
    import importlib_resources as resources


@functools.lru_cache()
def load_query(query_name) -> str:
    """Load a predefined GraphQL query and cache it."""
    assert query_name.endswith(".graphql")
    return resources.read_text("iot_inspector.queries", query_name)
