"""Asset checkpoint, copied from sekoia-automation-sdk `asset_connector/checkpoint.py`.

shortcut: copy of an SDK class not yet released, delete once the module uses `CheckpointedAssetConnector`.
"""

import time
from pathlib import Path
from typing import Literal

from sekoia_automation.storage import PersistentJSON

Cursor = str | int | float
CheckpointMode = Literal["incremental", "sweep"]


class AssetCheckpoint:
    """
    Cursor of a checkpointed asset connector.

    The connector yields its assets sorted ascending on the cursor. The cycle
    pushes a batch right after its last item is yielded, so the item staged last
    is the last item of the pushed batch when :meth:`commit` runs.

    Modes:
        incremental: resume after the stored cursor, forever.
        sweep: full passes. The cursor only resumes an interrupted pass; a
            completed pass clears it, and the next pass starts once `frequency`
            seconds have elapsed since the previous pass started.
    """

    FILE_NAME = "asset_checkpoint.json"

    def __init__(
        self,
        data_path: Path,
        mode: CheckpointMode,
    ) -> None:
        self.mode = mode
        self.store = PersistentJSON(self.FILE_NAME, data_path)
        self._start_cycle()

    def _start_cycle(self) -> None:
        self._safe: Cursor | None = None
        self._previous: Cursor | None = None
        self._previous_distinct: Cursor | None = None
        self._frozen = False
        self._unpushed = False
        self._exhausted = False

    @property
    def cursor(self) -> Cursor | None:
        with self.store as store:
            cursor: Cursor | None = store.get("cursor")
            return cursor

    def begin(self, frequency: int) -> tuple[bool, Cursor | None]:
        """
        Start a fetch cycle.

        Returns:
            tuple: whether to fetch in this cycle, and the cursor to fetch after.
        """
        self._start_cycle()
        if self.mode == "incremental":
            return True, self.cursor

        with self.store as store:
            started_at = store.get("pass_started_at")
            if started_at is not None and not store.get("pass_completed", False):
                return True, store.get("cursor")

            if started_at is not None and time.time() - started_at < frequency:
                return False, None

            store["cursor"] = None
            store["pass_started_at"] = time.time()
            store["pass_completed"] = False
        return True, None

    def stage(self, cursor: Cursor, next_cursor: Cursor | None) -> bool:
        """
        Record the item about to be yielded and the cursor of the item after it.

        A tie group cut by a push is not committed: with a strict `>` query it is
        fetched again whole on the next cycle instead of losing its tail.

        Returns:
            bool: True when this item reveals assets not sorted ascending. The
                checkpoint is then frozen until the end of the cycle.
        """
        self._unpushed = True

        if self._previous is not None and cursor != self._previous:
            self._previous_distinct = self._previous
        self._previous = cursor

        if self._frozen:
            return False

        # A connector yields a single cursor type.
        if next_cursor is not None and next_cursor < cursor:  # type: ignore[operator]
            self._frozen = True
            self._safe = None
            return True

        if next_cursor is None or next_cursor != cursor:
            self._safe = cursor
        else:
            self._safe = self._previous_distinct
        return False

    def commit(self) -> None:
        """Commit the cursor of the batch just pushed."""
        self._unpushed = False
        safe = self._safe
        if safe is not None:
            with self.store as store:
                stored = store.get("cursor")
                if stored is None or safe > stored:
                    store["cursor"] = safe

        if self._exhausted:
            self._complete_pass()

    def exhausted(self) -> None:
        """The connector yielded its last asset for this cycle."""
        self._exhausted = True
        if not self._unpushed:
            self._complete_pass()

    def _complete_pass(self) -> None:
        if self.mode != "sweep":
            return
        with self.store as store:
            store["cursor"] = None
            store["pass_completed"] = True

    def reset(self) -> None:
        """Forget the cursor: the next cycle fetches every asset again."""
        with self.store as store:
            store.clear()
        self._start_cycle()
