"""Unit tests for download object keys."""

from uuid import uuid4

import pytest
from app.modules.downloads.keys import chapter_object_key, combined_object_key, job_prefix


@pytest.mark.unit
def test_job_prefix_shape() -> None:
    user_id = uuid4()
    job_id = uuid4()
    assert job_prefix(user_id, job_id) == f"downloads/{user_id}/{job_id}/"

    user_id = uuid4()
    job_id = uuid4()
    assert chapter_object_key(user_id, job_id, 3) == (f"downloads/{user_id}/{job_id}/ch-3.mp3")


@pytest.mark.unit
def test_combined_object_key_shape() -> None:
    user_id = uuid4()
    job_id = uuid4()
    assert combined_object_key(user_id, job_id) == (f"downloads/{user_id}/{job_id}/combined.mp3")
