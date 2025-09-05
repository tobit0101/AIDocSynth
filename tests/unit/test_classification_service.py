import asyncio
import pytest
from unittest.mock import AsyncMock

from aidocsynth.services.classification_service import ClassificationService


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        {"target_directory": "T", "target_filename": "x.txt"},
        '{"target_directory": "T", "target_filename": "x.txt"}',
    ],
)
async def test_classify_document_success_cases(response):
    provider = AsyncMock()
    provider.classify_document = AsyncMock(return_value=response)
    svc = ClassificationService(provider)

    result = await svc.classify_document(
        text_content="hello",
        file_path="/tmp/dummy.pdf",
    )

    assert result == {"target_directory": "T", "target_filename": "x.txt"}


@pytest.mark.asyncio
async def test_classify_document_retries_until_valid():
    provider = AsyncMock()
    # First returns missing keys -> ValueError; second invalid JSON -> JSONDecodeError; third valid
    provider.classify_document = AsyncMock(side_effect=[
        '{"foo": 1}',
        'not json',
        {"target_directory": "T", "target_filename": "x.txt"},
    ])
    svc = ClassificationService(provider)

    result = await svc.classify_document(
        text_content="hello",
        file_path="/tmp/dummy.pdf",
    )

    assert result == {"target_directory": "T", "target_filename": "x.txt"}
    assert provider.classify_document.await_count == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario, side_effect",
    [
        ("missing_keys", ['{"foo": 1}', '{"bar": 2}', '{"baz": 3}']),
        ("invalid_json", ["not json", "still bad", "really bad"]),
        ("exception", [RuntimeError("boom"), RuntimeError("boom")]),
    ],
)
async def test_classify_document_fail_scenarios(scenario, side_effect):
    provider = AsyncMock()
    provider.classify_document = AsyncMock(side_effect=side_effect)
    svc = ClassificationService(provider)
    svc.max_retries = 2

    result = await svc.classify_document(
        text_content="hello",
        file_path="/tmp/dummy.pdf",
    )

    assert isinstance(result, dict)
    assert result.get("error") == "Classification failed"
    if scenario == "exception":
        # details should contain the last exception message
        assert "boom" in (result.get("details") or "")


@pytest.mark.asyncio
async def test_classify_document_cancelled_raises():
    provider = AsyncMock()
    provider.classify_document = AsyncMock(return_value={})
    svc = ClassificationService(provider)

    with pytest.raises(asyncio.CancelledError):
        await svc.classify_document(
            text_content="hello",
            file_path="/tmp/dummy.pdf",
            is_cancelled_callback=lambda: True,
        )

    # Provider should not be called if cancelled before attempt
    assert provider.classify_document.await_count == 0
