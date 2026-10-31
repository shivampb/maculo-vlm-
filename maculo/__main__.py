"""Run the server: python -m maculo"""

import logging

import uvicorn

from .config import get_settings


def main() -> None:
    s = get_settings()
    logging.basicConfig(
        level=s.log_level.upper(),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    uvicorn.run(
        "maculo.server:app",
        host=s.host,
        port=s.port,
        log_level=s.log_level,
        proxy_headers=s.trust_proxy,
        workers=1,  # each worker holds its own copy of the models
    )


if __name__ == "__main__":
    main()
