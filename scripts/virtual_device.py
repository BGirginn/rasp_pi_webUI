import asyncio
import random
import socket
import argparse
from aiohttp import web
from zeroconf import ServiceInfo, InterfaceChoice
from zeroconf.asyncio import AsyncZeroconf

# Configuration
DEVICE_NAME = "Virtual IoT Device"
SERVICE_TYPE = "_iot-device._tcp.local."
DEFAULT_PORT = 18080

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't need to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

class VirtualDevice:
    def __init__(self, port: int):
        self.ip = get_local_ip()
        self.port = port
        self.zeroconf = AsyncZeroconf(interfaces=InterfaceChoice.Default)
        self.service_info = None

    async def start_mdns(self):
        desc = {'version': '1.0.0', 'type': 'virtual'}
        
        self.service_info = ServiceInfo(
            SERVICE_TYPE,
            f"{DEVICE_NAME.replace(' ', '-')}.{SERVICE_TYPE}",
            addresses=[socket.inet_aton(self.ip)],
            port=self.port,
            properties=desc,
            server=f"{DEVICE_NAME.replace(' ', '-')}.local."
        )
        
        print(f"📡 Broadcasting mDNS service: {DEVICE_NAME} at {self.ip}:{self.port}")
        await self.zeroconf.async_register_service(self.service_info)

    async def stop_mdns(self):
        if self.service_info:
            await self.zeroconf.async_unregister_service(self.service_info)
        await self.zeroconf.async_close()

    async def handle_info(self, request):
        data = {
            "name": DEVICE_NAME,
            "status": "online",
            "sensors": [
                { "type": "temperature", "value": round(random.uniform(20, 30), 1), "unit": "°C" },
                { "type": "humidity", "value": round(random.uniform(40, 60), 1), "unit": "%" },
                { "type": "light", "value": int(random.uniform(300, 800)), "unit": "lux" },
                { "type": "voltage", "value": round(random.uniform(3.2, 4.2), 2), "unit": "V" },
                { "type": "signal_strength", "value": int(random.uniform(-80, -40)), "unit": "dBm" }
            ]
        }
        return web.json_response(data)

async def main(port: int):
    device = VirtualDevice(port)
    await device.start_mdns()

    app = web.Application()
    app.router.add_get('/info', device.handle_info)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', device.port)
    
    print(f"🚀 Virtual IoT Device running on http://{device.ip}:{device.port}")
    print("Press Ctrl+C to stop")
    
    await site.start()
    
    try:
        # Keep running
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        print("\nShutting down...")
        await device.stop_mdns()
        await runner.cleanup()

if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser(description="Run a virtual IoT device simulator.")
        parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"HTTP port to bind (default: {DEFAULT_PORT})")
        args = parser.parse_args()
        asyncio.run(main(args.port))
    except KeyboardInterrupt:
        pass
