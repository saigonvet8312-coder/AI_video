"""Chạy tác vụ nặng trên một luồng riêng và phát nhật ký trực tiếp lên giao diện."""
from __future__ import annotations

import queue
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

from .project import UserError

# Một luồng duy nhất: tuần tự hoá GPU và giữ Playwright trong cùng một luồng.
_EXECUTOR = ThreadPoolExecutor(max_workers=1)


def run_job(fn, *args, **kwargs):
    """Generator: yield (nhật_ký, kết_quả, lỗi). Hai giá trị cuối chỉ có ở lần yield cuối."""
    q: queue.Queue = queue.Queue()
    lines: list[str] = []
    fut = _EXECUTOR.submit(fn, *args, log=q.put, **kwargs)

    def drain():
        try:
            while True:
                lines.append(str(q.get_nowait()))
        except queue.Empty:
            pass

    while not fut.done():
        drain()
        yield "\n".join(lines[-300:]), None, None
        time.sleep(0.5)
    drain()

    err = None
    result = None
    try:
        result = fut.result()
    except UserError as e:
        err = f"⚠️ {e}"
    except Exception as e:  # noqa: BLE001
        tb = traceback.format_exc().strip().splitlines()[-6:]
        err = f"❌ Lỗi: {e}\n" + "\n".join(tb)
    if err:
        lines.append(err)
    yield "\n".join(lines[-300:]), result, err
