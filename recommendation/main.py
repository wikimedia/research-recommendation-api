import asyncio
import os
import sys
import traceback
from contextlib import asynccontextmanager

import psutil
from fastapi import FastAPI, Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException as StarletteHTTPException

from recommendation.api.translation.translation import router as translation_api_router
from recommendation.utils.cache_updater import (
    initialize_interwiki_map_cache,
    initialize_sitematrix_cache,
    update_page_collection_cache,
)
from recommendation.utils.configuration import configuration
from recommendation.utils.logger import log


async def periodic_cache_update():
    try:
        await initialize_interwiki_map_cache()
    except Exception as e:
        log.error(f"Failed to initialize interwiki map cache: {e}")
        return
    try:
        await initialize_sitematrix_cache()
    except Exception as e:
        log.error(f"Failed to initialize sitematrix cache: {e}")
        return
    while True:
        try:
            await update_page_collection_cache()
        except Exception as e:
            log.error(f"Failed to update page collection cache: {e}")
        await asyncio.sleep(60 * 60)  # Sleep for 1 hour


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Get the current process's parent process (Gunicorn parent process)
    parent_pid = os.getppid()

    try:
        # Use psutil to find the parent process
        parent_process = psutil.Process(parent_pid)
        # Get all child processes (workers)
        child_processes = parent_process.children()
        # Extract the PIDs of the children
        worker_pids = [child.pid for child in child_processes]

        # Get the PID of the current worker and its index in the list
        worker_id = os.getpid()
        worker_index = worker_pids.index(worker_id)

        if worker_index == 0:  # Execute the periodic task in the first worker only
            log.info(f"Starting up the {configuration.PROJECT_NAME}")
            cache_updater = asyncio.create_task(periodic_cache_update())
            yield
            cache_updater.cancel()
            log.info("Shutting down the service")
        else:
            yield
    except psutil.NoSuchProcess:
        log.error("Parent process not found. Worker lifespan setup will be skipped.")
        yield  # Proceed without periodic updates in this case

    except ValueError as e:
        log.error(f"Worker ID not found in the list of worker PIDs: {e}")
        yield  # Proceed even if worker ID is not in the list

    except Exception as e:
        log.exception(f"An unexpected error occurred in the lifespan context: {e}")
        yield  # Ensure the app doesn't crash due to unhandled exceptions


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


app = FastAPI(
    title=configuration.PROJECT_NAME,
    lifespan=lifespan,
    debug=configuration.DEBUG,
    version=configuration.PROJECT_VERSION,
    root_path=configuration.API_PREFIX,
    servers=[
        {"url": "https://recommend.wmcloud.org/", "description": "Staging environment"},
        {"url": "https://api.wikimedia.org", "description": "Production environment"},
    ],
)
app.include_router(
    translation_api_router,
    prefix=f"/{configuration.API_VERSION}",
    tags=["translation"],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/")
async def homepage_redirect():
    response = RedirectResponse(url="/docs")
    return response


# Custom error handlers
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request, exc):
    return await http_exception_handler(request, exc)


@app.exception_handler(ValueError)
async def value_error_exception_handler(request: Request, exc: ValueError):
    return await request_validation_exception_handler(request, exc)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return await request_validation_exception_handler(request, exc)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> PlainTextResponse:
    """
    This middleware will log all unhandled exceptions.
    Unhandled exceptions are all exceptions that are not HTTPExceptions or RequestValidationErrors.
    """

    url = f"{request.url.path}?{request.query_params}" if request.query_params else request.url.path
    exception_type, exc_value, exception_traceback = sys.exc_info()
    exc_name = getattr(exception_type, "__name__", None)
    trace = "".join(traceback.format_tb(exception_traceback))
    exc_details = f'{url}" 500 Internal Server Error <{exc_name}: {exc_value}>'
    log.error(f"{exc_details} Trace: {trace}")
    return PlainTextResponse(exc_details, status_code=500)


def start():
    import uvicorn

    """Launched with `poetry run start` at root level"""
    uvicorn.run("recommendation.main:app", host="0.0.0.0", port=8000, reload=True)
