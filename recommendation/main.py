import asyncio
import os
import sys
import traceback
from contextlib import asynccontextmanager

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
from recommendation.utils.cache_updater import update_page_collection_cache
from recommendation.utils.configuration import configuration
from recommendation.utils.logger import log


async def periodic_cache_update():
    while True:
        await asyncio.sleep(60 * 60)  # Sleep for 1 hour
        await update_page_collection_cache()


@asynccontextmanager
async def lifespan(app: FastAPI):
    worker_id = os.getpid()
    # TODO: Use env variable for number of workers
    number_of_workers = 4
    if worker_id % number_of_workers == 0:  # we are using 4
        log.info(f"Starting up the {configuration.PROJECT_NAME}")
        await update_page_collection_cache()
        cache_updater = asyncio.create_task(periodic_cache_update())
        yield

        cache_updater.cancel()
        log.info("Shutting down the service")
    else:
        yield


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
