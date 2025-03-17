import logging

from fastapi import FastAPI


logger = logging.getLogger("asgi")

fastapi_app = FastAPI(docs_url="/doc")


@fastapi_app.get("/foo")
async def foo() -> dict[str, str]:
    logger.info("hello")
    return {"foo": "bar"}
