from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from engine.curriculum.models import ProgressState

DEFAULT_PROGRESS_PATH = "curriculum/progress.json"


class ProgressStore:
    def __init__(self, path: str = DEFAULT_PROGRESS_PATH) -> None:
        self._path = path

    def load(self) -> ProgressState:
        if not os.path.exists(self._path):
            return ProgressState()

        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            bak_path = f"{self._path}.bak"
            if os.path.exists(self._path):
                os.replace(self._path, bak_path)
            return ProgressState()

        return ProgressState.from_dict(data)

    def mark_complete(self, lesson_id: str) -> None:
        state = self.load()
        if lesson_id not in state.completed:
            state.completed.append(lesson_id)
        state.last_lesson_id = lesson_id
        state.updated_at = datetime.now(timezone.utc).isoformat()
        self._save(state)

    def _save(self, state: ProgressState) -> None:
        parent = os.path.dirname(self._path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)
