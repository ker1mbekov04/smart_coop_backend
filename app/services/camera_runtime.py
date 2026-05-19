import asyncio
import time


class CameraRuntime:
    def __init__(self):
        self.frame = None
        self.frame_time = None
        self.frame_size = None
        self.event = asyncio.Event()

    async def set_frame(self, frame: bytes):
        self.frame = frame
        self.frame_time = time.time()
        self.frame_size = len(frame)
        self.event.set()
        self.event = asyncio.Event()

    async def wait_frame(self, timeout=2):
        try:
            await asyncio.wait_for(self.event.wait(), timeout)
        except asyncio.TimeoutError:
            return None
        return self.frame


camera_runtime = CameraRuntime()
