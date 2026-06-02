"""
Tests for gather_with_concurrency, the shared-semaphore bounded-concurrency helper.

The key guarantee is that no more than ``limit`` awaitables run at once. The earlier
collection-fetch code created a fresh semaphore *inside* each coroutine, so it never
actually bounded concurrency; these tests would fail against that pattern.
"""

import asyncio

import pytest

from recommendation.utils.async_helper import gather_with_concurrency


@pytest.mark.asyncio(loop_scope="session")
async def test_respects_concurrency_limit():
    limit = 3
    in_flight = 0
    peak = 0

    async def task(value):
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        # Yield control so other tasks get a chance to start if the limit allowed it.
        await asyncio.sleep(0.01)
        in_flight -= 1
        return value

    results = await gather_with_concurrency(limit, [task(i) for i in range(20)])

    assert results == list(range(20))
    assert peak <= limit
    # Sanity check that we did run concurrently up to the limit (not serialized).
    assert peak == limit


@pytest.mark.asyncio(loop_scope="session")
async def test_preserves_order():
    async def task(value):
        # Smaller values sleep longer, so completion order differs from input order.
        await asyncio.sleep((10 - value) * 0.001)
        return value

    results = await gather_with_concurrency(5, [task(i) for i in range(10)])

    assert results == list(range(10))


@pytest.mark.asyncio(loop_scope="session")
async def test_returns_exceptions_by_default():
    async def ok():
        return "ok"

    async def boom():
        raise ValueError("boom")

    results = await gather_with_concurrency(2, [ok(), boom(), ok()])

    assert results[0] == "ok"
    assert isinstance(results[1], ValueError)
    assert results[2] == "ok"


@pytest.mark.asyncio(loop_scope="session")
async def test_can_propagate_exceptions():
    async def boom():
        raise ValueError("boom")

    with pytest.raises(ValueError):
        await gather_with_concurrency(2, [boom()], return_exceptions=False)


@pytest.mark.asyncio(loop_scope="session")
async def test_empty_input():
    results = await gather_with_concurrency(5, [])
    assert results == []
