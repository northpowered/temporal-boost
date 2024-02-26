from fastapi import FastAPI, Response


async def foo():
    return Response(status_code=200)

fastapi_app: FastAPI = FastAPI(docs_url="/doc")

fastapi_app.add_api_route("/foo", foo)