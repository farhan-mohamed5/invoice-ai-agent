from __future__ import annotations

import email
import imaplib
import os
import sys
import time
from email.header import decode_header
from pathlib import Path
from typing import List

_THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT: Path | None = None
for parent in _THIS_FILE.parents:
    if (parent / "apps").is_dir():
        PROJECT_ROOT = parent
        break

if PROJECT_ROOT is None:
    PROJECT_ROOT = _THIS_FILE.parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv  # pip install python-dotenv
except Exception:
    load_dotenv = None

if load_dotenv is not None:
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)  

from apps.worker.pipeline.config import ALLOWED_EXTS, INBOX_DIR
from apps.worker.pipeline.services_ocr_llm import classify_email_text


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


IMAP_HOST = _env("INVOICE_AGENT_IMAP_HOST") or _env("RECEIPT_AGENT_IMAP_HOST", "imap.gmail.com")
IMAP_USER = _env("INVOICE_AGENT_IMAP_USER") or _env("RECEIPT_AGENT_IMAP_USER", "")
IMAP_PASSWORD = _env("INVOICE_AGENT_IMAP_PASSWORD") or _env("RECEIPT_AGENT_IMAP_PASSWORD", "")
IMAP_FOLDER = _env("INVOICE_AGENT_IMAP_FOLDER") or _env("RECEIPT_AGENT_IMAP_FOLDER", "INBOX")
IMAP_POLL_SECONDS = int(
    _env("INVOICE_AGENT_IMAP_POLL_SECONDS") or _env("RECEIPT_AGENT_IMAP_POLL_SECONDS", "60")
)


def _decode_mime_words(s: str) -> str:
    decoded_fragments = []
    for frag, charset in decode_header(s):
        if isinstance(frag, bytes):
            decoded_fragments.append(frag.decode(charset or "utf-8", errors="replace"))
        else:
            decoded_fragments.append(frag)
    return "".join(decoded_fragments)


def _connect_imap() -> imaplib.IMAP4_SSL:
    if not IMAP_USER or not IMAP_PASSWORD:
        raise RuntimeError(
            "IMAP credentials not configured. Set INVOICE_AGENT_IMAP_USER and "
            "INVOICE_AGENT_IMAP_PASSWORD (Gmail App Password) in your .env."
        )
    imap = imaplib.IMAP4_SSL(IMAP_HOST)
    imap.login(IMAP_USER, IMAP_PASSWORD)
    return imap


def _get_text_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "").lower()
            if ctype == "text/plain" and "attachment" not in disp:
                try:
                    return part.get_payload(decode=True).decode(
                        part.get_content_charset() or "utf-8",
                        errors="replace",
                    )
                except Exception:
                    continue
    else:
        try:
            return msg.get_payload(decode=True).decode(
                msg.get_content_charset() or "utf-8", errors="replace"
            )
        except Exception:
            return ""
    return ""


def _body_contains_invoice(body: str) -> bool:
    text = (body or "").lower()
    invoice_signals = [
        "invoice",
        "tax invoice",
        "amount due",
        "total amount",
        "grand total",
        "balance due",
        "outstanding",
        "vat",
        "trn",
        "aed",
        "paid",
    ]
    hits = sum(1 for k in invoice_signals if k in text)
    return hits >= 3


def _save_attachments(msg: email.message.Message) -> List[Path]:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    saved_paths: List[Path] = []

    for part in msg.walk():
        disp = str(part.get("Content-Disposition") or "").lower()
        if "attachment" not in disp:
            continue

        filename = part.get_filename()
        if not filename:
            continue

        filename_decoded = _decode_mime_words(filename)
        suffix = Path(filename_decoded).suffix.lower()
        if suffix not in ALLOWED_EXTS:
            continue

        data = part.get_payload(decode=True)
        if data is None:
            continue

        out_path = INBOX_DIR / filename_decoded
        counter = 1
        while out_path.exists():
            stem = Path(filename_decoded).stem
            out_path = INBOX_DIR / f"{stem}-{counter}{suffix}"
            counter += 1

        with open(out_path, "wb") as f:
            f.write(data)

        saved_paths.append(out_path)

    return saved_paths


def _mark_seen(imap: imaplib.IMAP4_SSL, uid: bytes) -> None:
    try:
        imap.store(uid, "+FLAGS", "\\Seen")
    except Exception:
        pass


def process_unseen() -> None:
    imap = _connect_imap()
    try:
        imap.select(IMAP_FOLDER)
        status, data = imap.search(None, "UNSEEN")
        if status != "OK":
            print(f"[IMAP] search failed: {status}")
            return

        ids = data[0].split()
        print(f"[IMAP] Found {len(ids)} unseen emails.")

        for uid in ids:
            status, msg_data = imap.fetch(uid, "(RFC822)")
            if status != "OK":
                print(f"[IMAP] Failed to fetch UID {uid!r}")
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            subject = _decode_mime_words(msg.get("Subject") or "")
            from_ = _decode_mime_words(msg.get("From") or "")
            body = _get_text_body(msg)

            try:
                clf = classify_email_text(subject, body)
            except Exception as e:
                text = f"{subject}\n{body}".lower()
                clf = (
                    "INVOICE"
                    if any(k in text for k in ("invoice", "tax invoice", "receipt", "statement"))
                    else "OTHER"
                )
                print(f"[IMAP] Classifier error, using fallback: {e}")

            print(f"[IMAP] UID {uid.decode()}: {clf} – From: {from_} | Subject: {subject}")

            if clf != "INVOICE":
                continue

            if _body_contains_invoice(body):
                INBOX_DIR.mkdir(parents=True, exist_ok=True)
                safe_subject = subject.replace("/", "_").replace("\\", "_").strip()
                out_path = INBOX_DIR / f"email_body_{safe_subject}.txt"

                counter = 1
                while out_path.exists():
                    out_path = INBOX_DIR / f"email_body_{safe_subject}-{counter}.txt"
                    counter += 1

                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(body)

                print(f"[IMAP] Saved invoice from email body: {out_path}")
                _mark_seen(imap, uid)
                continue

            attachments = _save_attachments(msg)
            for p in attachments:
                print(f"[IMAP] Saved invoice attachment to inbox: {p}")
            if attachments:
                _mark_seen(imap, uid)

    finally:
        try:
            imap.close()
        except Exception:
            pass
        imap.logout()


def run_forever(poll_seconds: int) -> None:
    user_display = IMAP_USER or "<missing>"
    print(
        f"[IMAP] Live mode enabled. Polling every {poll_seconds}s | Host={IMAP_HOST} | Folder={IMAP_FOLDER} | User={user_display}"
    )
    while True:
        try:
            process_unseen()
        except Exception as e:
            print(f"[IMAP] Poll error: {e}")
        time.sleep(poll_seconds)


if __name__ == "__main__":
    live = (
        (_env("INVOICE_AGENT_IMAP_LIVE") or _env("RECEIPT_AGENT_IMAP_LIVE") or "")
        .strip()
        .lower()
        in {"1", "true", "yes", "y"}
    )
    if live:
        run_forever(IMAP_POLL_SECONDS)
    else:
        process_unseen()