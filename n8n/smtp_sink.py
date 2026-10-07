"""Local SMTP sink for testing the n8n workflow: accepts mail on 127.0.0.1:1025 and writes each
message to output/handoff/ instead of delivering it. Nothing leaves the machine.

    python n8n/smtp_sink.py
"""

import asyncio
import email
import re
from email import policy
from pathlib import Path

from aiosmtpd.controller import Controller

OUT = Path(__file__).resolve().parent.parent / "output" / "handoff"


class Sink:
    async def handle_DATA(self, server, session, envelope):
        OUT.mkdir(parents=True, exist_ok=True)
        msg = email.message_from_bytes(envelope.content, policy=policy.default)
        n = len(list(OUT.glob("*.eml"))) + 1
        slug = re.sub(r"[^a-z0-9]+", "-", (msg["subject"] or "").lower())[:50].strip("-")
        (OUT / f"{n:02d}-{slug}.eml").write_bytes(envelope.content)
        body = msg.get_body(preferencelist=("plain", "html"))
        lines = [f"From: {msg['from']}", f"To: {msg['to']}", f"Subject: {msg['subject']}",
                 "Attachments: " + ", ".join(p.get_filename() or "?" for p in msg.iter_attachments()), "",
                 body.get_content() if body else ""]
        (OUT / f"{n:02d}-{slug}.txt").write_text("\n".join(lines))
        return "250 Message accepted for delivery (captured locally)"


async def main():
    Controller(Sink(), hostname="127.0.0.1", port=1025).start()
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
