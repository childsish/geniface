from __future__ import annotations

from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default
from io import BytesIO


@dataclass
class MiniFieldStorage:
    name: str
    value: str
    filename: str | None = None
    file: BytesIO | None = None


class FieldStorage:
    def __init__(self, fp, headers=None, environ=None):
        environ = environ or {}
        content_type = environ.get("CONTENT_TYPE", "")
        content_length = int(environ.get("CONTENT_LENGTH", "0"))
        body = fp.read(content_length)
        raw_message = (
            f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
            + body
        )
        message = BytesParser(policy=default).parsebytes(raw_message)
        self.list = []

        for part in message.iter_parts():
            name = part.get_param("name", header="content-disposition")
            if not name:
                continue

            filename = part.get_filename()
            payload = part.get_payload(decode=True) or b""
            if filename is not None:
                self.list.append(
                    MiniFieldStorage(
                        name=name,
                        value="",
                        filename=filename,
                        file=BytesIO(payload),
                    )
                )
                continue

            self.list.append(
                MiniFieldStorage(
                    name=name,
                    value=payload.decode(part.get_content_charset() or "utf-8"),
                )
            )
