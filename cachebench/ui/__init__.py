"""Interface web locale : lance les commandes de cachebench depuis un navigateur."""
from .server import make_server, serve

__all__ = ["make_server", "serve"]
