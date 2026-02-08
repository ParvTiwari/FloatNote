import asyncio
import websockets
import json

async def main():
    async with websockets.connect("ws://127.0.0.1:8000/ws/stt", open_timeout=5) as ws:
        try:
            print("Connected!")
            while True:
                msg = await ws.recv()
                print(msg)
                # data = json.loads(msg)

                # print("\nText:", data["text"])
                # print("Keywords:", data["keywords"])
                # print("Intent:", data["intent"])
        except Exception as e:
            print("Failed to connect:", e)

asyncio.run(main())