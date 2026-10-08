"""Debounced host event monitors that trigger resource rediscovery."""

import asyncio
import shutil
from typing import Awaitable, Callable, List, Optional

import structlog


logger = structlog.get_logger(__name__)


class EventMonitor:
    def __init__(self, refresh: Callable[[], Awaitable[object]], debounce_seconds: float = 0.75):
        self._refresh = refresh
        self._debounce_seconds = debounce_seconds
        self._tasks: List[asyncio.Task] = []
        self._processes: List[asyncio.subprocess.Process] = []
        self._debounce_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        commands = [
            ["udevadm", "monitor", "--udev", "--property"],
            ["nmcli", "monitor"],
            ["busctl", "monitor", "org.freedesktop.systemd1"],
        ]
        for command in commands:
            if shutil.which(command[0]):
                self._tasks.append(asyncio.create_task(self._watch(command)))
        logger.info("Host event monitors started", count=len(self._tasks))

    async def stop(self) -> None:
        self._running = False
        if self._debounce_task:
            self._debounce_task.cancel()
        processes = list(self._processes)
        for process in processes:
            if process.returncode is None:
                process.terminate()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        for process in processes:
            if process.returncode is None:
                try:
                    await asyncio.wait_for(process.wait(), timeout=2)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
        self._tasks.clear()
        self._processes.clear()

    async def _watch(self, command: List[str]) -> None:
        while self._running:
            process = None
            try:
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    limit=256 * 1024,
                )
                self._processes.append(process)
                assert process.stdout is not None
                while self._running:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    self._signal_refresh()
                await process.wait()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Host event monitor failed", command=command[0], error=str(exc))
            finally:
                if process in self._processes:
                    self._processes.remove(process)
                if process and process.returncode is None:
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=2)
                    except asyncio.TimeoutError:
                        process.kill()
                        await process.wait()
            if self._running:
                await asyncio.sleep(2)

    def _signal_refresh(self) -> None:
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()
        self._debounce_task = asyncio.create_task(self._debounced_refresh())

    async def _debounced_refresh(self) -> None:
        try:
            await asyncio.sleep(self._debounce_seconds)
            await self._refresh()
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.warning("Event-triggered discovery failed", error=str(exc))
