import uvicorn
from backend.config import ServerConfig
from backend.server import app

if __name__ == "__main__":
    _cfg = ServerConfig.load()
    uvicorn.run("backend.server:app", host=_cfg.host, port=_cfg.port, reload=False)
