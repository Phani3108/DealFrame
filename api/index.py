from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def root():
    return {"status": "ok", "service": "dealframe"}


@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}


@app.get("/{path:path}")
async def catch_all(path: str = ""):
    return {"path": path, "status": "dealframe is running"}
