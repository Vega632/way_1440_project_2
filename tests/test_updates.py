import asyncio
import unittest
from types import SimpleNamespace
from bot.updates import PerUserProcessor


class ProcessorTests(unittest.IsolatedAsyncioTestCase):
    async def test_other_users_continue_but_same_user_waits(self):
        processor = PerUserProcessor()
        await processor.initialize()
        entered = asyncio.Event()
        release = asyncio.Event()
        seen = []

        async def slow():
            entered.set()
            await release.wait()
            seen.append("first")

        async def fast(label):
            seen.append(label)

        user1 = SimpleNamespace(effective_user=SimpleNamespace(id=1))
        user2 = SimpleNamespace(effective_user=SimpleNamespace(id=2))
        first = asyncio.create_task(processor.process_update(user1, slow()))
        await entered.wait()
        second = asyncio.create_task(processor.process_update(user1, fast("second")))
        await processor.process_update(user2, fast("other"))
        self.assertEqual(seen, ["other"])
        release.set()
        await asyncio.gather(first, second)
        self.assertEqual(seen, ["other", "first", "second"])
        await processor.shutdown()
