"""pytest configuration for the test suite."""
import pytest


# Allow all async tests to run without manually adding @pytest.mark.asyncio
# to every individual test method.
def pytest_collection_modifyitems(items):
    for item in items:
        if item.get_closest_marker("asyncio") is None:
            if hasattr(item, "function") and hasattr(item.function, "__wrapped__"):
                pass
