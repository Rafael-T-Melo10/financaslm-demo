import os

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("UVICORN_HOST", "0.0.0.0")
    port = int(os.getenv("UVICORN_PORT", "8000"))
    reload_enabled = os.getenv("UVICORN_RELOAD", "false").lower() == "true"

    uvicorn.run("app.main:app", host=host, port=port, reload=reload_enabled)
