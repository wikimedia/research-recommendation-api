import asyncio
from typing import Awaitable, Iterable, List


async def gather_with_concurrency(limit: int, coros: Iterable[Awaitable], *, return_exceptions: bool = True) -> List:
    """
    Run the given awaitables concurrently, with at most ``limit`` of them in flight at any time.

    A single shared semaphore bounds the concurrency for the whole batch. This is the
    correct pattern: creating a fresh semaphore *per coroutine* provides no limiting at
    all, since each coroutine acquires its own, always-free semaphore.

    Args:
        limit: Maximum number of awaitables allowed to run concurrently.
        coros: The awaitables to run.
        return_exceptions: Passed through to ``asyncio.gather``. When True (the default),
            exceptions are returned in the result list rather than propagated.

    Returns:
        The list of results, in the same order as ``coros``.
    """
    semaphore = asyncio.Semaphore(limit)

    async def _run(coro: Awaitable):
        async with semaphore:
            return await coro

    return await asyncio.gather(*(_run(coro) for coro in coros), return_exceptions=return_exceptions)
