"""ASGI entry point. Production must inject a real identity adapter before use."""

from .main import create_app

app = create_app()
