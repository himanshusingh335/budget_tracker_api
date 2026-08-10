import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn

from core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "api.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_config=None,
    )
