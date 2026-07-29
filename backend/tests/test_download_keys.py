"""Unit tests for download object keys."""

from uuid import UUID, uuid4

import pytest
from app.modules.downloads.keys import (
    chapter_object_key,
    combined_object_key,
    download_filename,
    job_prefix,
)


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


@pytest.mark.unit
def test_download_filename_includes_book_range_and_unique_suffix() -> None:
    job_id = UUID("12345678-1234-5678-1234-567812345678")

    assert download_filename("I Have: Awesome/Luck?", 4, 12, job_id) == (
        "I-Have-Awesome-Luck-chapters-4-12-12345678.mp3"
    )
    assert download_filename("Genius", 7, 7, job_id) == "Genius-chapter-7-12345678.mp3"
