import logging

from fastapi import FastAPI


logger = logging.getLogger("asgi")

fastapi_app = FastAPI(docs_url=None, openapi_url=None)


@fastapi_app.get("/foo")
async def foo() -> dict[str, str]:
    logger.info("hello")
    return {"foo": "bar"}
