from __future__ import annotations

import time
from pathlib import Path

from apps.worker.pipeline.config import INBOX_DIR, ALLOWED_EXTS, DB_PATH, OUTPUT_ROOT
from apps.worker.pipeline.core_pipeline import bootstrap, process_single_invoice

try:
    from watchdog.observers import Observer  # type: ignore
    from watchdog.events import FileSystemEventHandler  # type: ignore
except ImportError:  # pragma: no cover
    Observer = None  # type: ignore
    FileSystemEventHandler = object  # type: ignore


class InboxHandler(FileSystemEventHandler):  # type: ignore[misc]
    def on_created(self, event):
        if event.is_directory:
            return

        path = Path(event.src_path)
        if path.suffix.lower() not in ALLOWED_EXTS and path.suffix.lower() != ".txt":
            return

        print(f"[WATCHER] New file: {path.name}")
        try:
            src = "email_body" if path.suffix.lower() == ".txt" else "local"
            process_single_invoice(path, source=src)
            print(f"[OK] Processed {path.name}")
        except Exception as exc:
            print(f"[ERROR] Failed to process {path.name}: {exc!r}")


def start_watcher(poll_fallback: bool = True) -> None:
    """
    Start folder watcher on INBOX_DIR.
    If watchdog isn't available, use a simple polling loop.
    """
    bootstrap()

    if Observer is None:
        if not poll_fallback:
            raise RuntimeError("watchdog is not installed; cannot start watcher.")
        print("[WATCHER] watchdog not installed – falling back to polling loop.")
        _poll_loop()
        return

    print(f"[WATCHER] Watching inbox folder: {INBOX_DIR}")
    event_handler = InboxHandler()
    observer = Observer()
    observer.schedule(event_handler, str(INBOX_DIR), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("[WATCHER] Stopping…")
        observer.stop()
        observer.join()


def _poll_loop(interval: float = 3.0) -> None:
    """Very simple polling loop for environments without watchdog."""
    seen = set()
    print(f"[WATCHER] Polling inbox folder every {interval}s: {INBOX_DIR}")

    while True:
        try:
            for path in INBOX_DIR.iterdir():
                if not path.is_file():
                    continue
                if path.suffix.lower() not in ALLOWED_EXTS and path.suffix.lower() != ".txt":
                    continue
                if path in seen:
                    continue

                seen.add(path)
                print(f"[WATCHER] New file (poll): {path.name}")
                try:
                    src = "email_body" if path.suffix.lower() == ".txt" else "local"
                    process_single_invoice(path, source=src)
                    print(f"[OK] Processed {path.name}")
                except Exception as exc:
                    print(f"[ERROR] Failed to process {path.name}: {exc!r}")

            time.sleep(interval)
        except KeyboardInterrupt:
            print("[WATCHER] Stopping polling loop…")
            return


def main() -> None:
    print("=== Invoice Filing Agent ===")
    print(f"DB:      {DB_PATH}")
    print(f"Inbox:   {INBOX_DIR}")
    print(f"Output:  {OUTPUT_ROOT}")
    start_watcher()


if __name__ == "__main__":
    main()