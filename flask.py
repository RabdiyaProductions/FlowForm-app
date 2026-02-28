import json
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Response:
    status_code: int
    _payload: Any

    def get_json(self) -> Any:
        return self._payload


class Flask:
    def __init__(self, import_name: str):
        self.import_name = import_name
        self.config: dict[str, Any] = {}
        self._routes: dict[tuple[str, str], Callable[..., Any]] = {}

    def get(self, path: str):
        def decorator(func: Callable[..., Any]):
            self._routes[("GET", path)] = func
            return func

        return decorator

    def run(self, debug: bool = False):
        raise RuntimeError("Local stub Flask does not provide a production server")

    def test_client(self):
        return _TestClient(self)


class _TestClient:
    def __init__(self, app: Flask):
        self._app = app

    def get(self, path: str):
        handler = self._app._routes.get(("GET", path))
        if handler is None:
            return Response(404, {"error": "not found"})

        payload = handler()
        if isinstance(payload, Response):
            return payload
        return Response(200, payload)


def jsonify(payload: Any):
    json.dumps(payload)
    return payload
