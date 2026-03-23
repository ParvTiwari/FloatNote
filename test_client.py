import asyncio
import websockets

async def test_my_code():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as websocket:
        print("🔌 Connected to server!")
        
        fake_audio = b'\x00' * 1024 
        await websocket.send(fake_audio)
        
        response = await websocket.recv()
        print(f"📨 Server replied: {response}")

if __name__ == "__main__":
    asyncio.run(test_my_code())