from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("startup: open pools/clients")
    app.state.resource = "ready"
    yield
    print("shutdown: drain and close resources")


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root():
    return {"resource": app.state.resource}


with TestClient(app) as client:
    print(client.get("/").json())
