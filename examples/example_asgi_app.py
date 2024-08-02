from fastapi import FastAPI, Response

fastapi_app: FastAPI = FastAPI(docs_url="/doc")


async def foo():
    fastapi_app.logger.info("hello", trace_id=123)
    return Response(status_code=200)


fastapi_app.add_api_route("/foo", foo)
