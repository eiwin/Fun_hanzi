import os

import uvicorn


if __name__ == "__main__":
    host = os.getenv("FUN_HANZI_HOST", "0.0.0.0")
    port = int(os.getenv("FUN_HANZI_PORT", "8000"))
    uvicorn.run("backend.app:app", host=host, port=port, reload=False)
