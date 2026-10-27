"""Process different users concurrently while preserving each dialogue's order."""

import asyncio
from telegram.ext import BaseUpdateProcessor


class PerUserProcessor(BaseUpdateProcessor):
    def __init__(self, max_concurrent_updates=16):
        super().__init__(max_concurrent_updates)
        self.locks = {}

    async def initialize(self):
        pass

    async def shutdown(self):
        self.locks.clear()

    async def do_process_update(self, update, coroutine):
        user = getattr(update, "effective_user", None)
        key = user.id if user else None
        lock = self.locks.setdefault(key, asyncio.Lock())
        async with lock:
            await coroutine
