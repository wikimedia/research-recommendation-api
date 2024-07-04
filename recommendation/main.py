from fastapi import FastAPI, Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException as StarletteHTTPException

from recommendation.api.translation.translation import router as translation_api_router
from recommendation.utils.configuration import configuration


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


app = FastAPI(
    title=configuration.PROJECT_NAME,
    debug=False,
    version=configuration.PROJECT_VERSION,
)
app.include_router(
    translation_api_router,
    prefix=f"{configuration.API_PREFIX}/{configuration.API_VERSION}",
    tags=["translation"],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


# Custom error handlers
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request, exc):
    return await http_exception_handler(request, exc)


@app.exception_handler(ValueError)
async def value_error_exception_handler(request: Request, exc: ValueError):
    return await request_validation_exception_handler(request, exc)


def start():
    import uvicorn

    """Launched with `poetry run start` at root level"""
    uvicorn.run("recommendation.main:app", host="0.0.0.0", port=8000, reload=True)
