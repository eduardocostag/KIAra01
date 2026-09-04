from __future__ import annotations

import asyncio
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.event_bus import EventBus
from app.perception import ScreenPerception


async def main() -> int:
    perception = ScreenPerception(EventBus())
    capture = await perception.capture_virtual_desktop()
    if capture is None or not capture.png:
        print("SCREEN_CAPTURE_OK=False")
        return 2
    signature = hashlib.sha256(capture.png).hexdigest()[:12]
    print(
        f"SCREEN_CAPTURE_OK=True WIDTH={capture.width} HEIGHT={capture.height} "
        f"SIGNATURE={signature} PERSISTED=False"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
