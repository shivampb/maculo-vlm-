"""ASGI entry point: uvicorn maculo.server:app"""

from .api import create_app

app = create_app()
