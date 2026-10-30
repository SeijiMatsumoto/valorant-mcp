import json
from pathlib import Path


class MatchCache:
    """Disk cache of completed match payloads, keyed by match id.

    Finished matches never change, so entries never expire.
    """

    def __init__(self, cache_dir: Path):
        self.dir = cache_dir / "matches"

    def _path(self, match_id: str) -> Path:
        return self.dir / f"{match_id}.json"

    def get(self, match_id: str) -> dict | None:
        path = self._path(match_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return None

    def put(self, match: dict) -> None:
        meta = match.get("metadata") or {}
        match_id = meta.get("match_id")
        if not match_id or not meta.get("is_completed", True):
            return
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            self._path(match_id).write_text(json.dumps(match))
        except OSError:
            pass
