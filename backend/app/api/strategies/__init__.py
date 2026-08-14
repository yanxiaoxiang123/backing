"""Strategy API package.

``routes.py`` holds the endpoints; ``schemas.py`` the request/response DTOs.
Importing the package exposes ``router`` for ``main.py``.
"""

from app.api.strategies.routes import router

__all__ = ["router"]
