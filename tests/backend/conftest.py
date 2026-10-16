from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from scripts.seed_synthetic_data import load_demo_course_content, load_synthetic_data

from skillpulse.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def demo_course_content() -> None:
    """Load the synthetic dataset plus the demo module checks and final project."""
    load_synthetic_data()
    load_demo_course_content()
