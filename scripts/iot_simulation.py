import asyncio
import random
import socket
import logging
from typing import List, Dict
from aiohttp import web
from zeroconf import ServiceInfo, Zeroconf

# Encode logging to avoid encoding errors on some systems
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

SERVICE_TYPE = "_iot-device._tcp.local."
BASE_PORT = 8090

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
    def __init__(self, name: str, port: int, sensor_templates: List[Dict]):
        self.name = name
        self.port = port
        self.sensor_templates = sensor_templates
        self.ip = get_local_ip()
        self.zeroconf = Zeroconf()
        self.service_info = None

    def generate_sensor_data(self):
        sensors = []
        for temp in self.sensor_templates:
            # Generate random value based on range if provided, or defaults
            stype = temp.get("type")
            
            if stype == "temperature":
                val = round(random.uniform(18, 30), 1)
                unit = "°C"
            elif stype == "humidity":
                val = round(random.uniform(30, 70), 1)
                unit = "%"
            elif stype == "light":
                val = int(random.uniform(0, 1000))
                unit = "lux"
            elif stype == "voltage":
                val = round(random.uniform(3.0, 4.2), 2)
                unit = "V"
            elif stype == "co2":
                val = int(random.uniform(400, 1200))
                unit = "ppm"
            elif stype == "pressure":
                val = int(random.uniform(980, 1020))
                unit = "hPa"
            elif stype == "noise":
                val = int(random.uniform(30, 90))
                unit = "dB"
            elif stype == "soil_moisture":
                val = int(random.uniform(0, 100))
                unit = "%"
            else:
                val = random.randint(0, 100)
                unit = ""

            sensors.append({
                "type": stype,
                "value": val,
                "unit": unit
            })
        return sensors

    async def handle_info(self, request):
        data = {
            "name": self.name,
            "status": "online",
            "sensors": self.generate_sensor_data()
        }
        return web.json_response(data)

    async def start(self):
        # Setup mDNS
        clean_name = self.name.lower().replace(' ', '-')
        desc = {'version': '1.0.0', 'type': 'simulation'}
        
        self.service_info = ServiceInfo(
            SERVICE_TYPE,
            f"{clean_name}.{SERVICE_TYPE}",
            addresses=[socket.inet_aton(self.ip)],
            port=self.port,
            properties=desc,
            server=f"{clean_name}.local."
        )
        
        logger.info(f"Starting {self.name} on port {self.port}...")
        self.zeroconf.register_service(self.service_info)

        # Setup Web Server
        app = web.Application()
        app.router.add_get('/info', self.handle_info)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.port)
        await site.start()
        
        return runner

    def stop(self):
        if self.service_info:
            self.zeroconf.unregister_service(self.service_info)
        self.zeroconf.close()

async def main():
    devices_config = [
        {
            "name": "Living Room",
            "sensors": [{"type": "temperature"}, {"type": "humidity"}, {"type": "co2"}]
        },
        {
            "name": "Kitchen",
            "sensors": [{"type": "temperature"}, {"type": "gas"}, {"type": "smoke"}]
        },
        {
            "name": "Garden Station",
            "sensors": [{"type": "temperature"}, {"type": "humidity"}, {"type": "soil_moisture"}, {"type": "light"}]
        },
        {
            "name": "Server Room",
            "sensors": [{"type": "temperature"}, {"type": "noise"}, {"type": "voltage"}]
        },
        {
            "name": "Balcony",
            "sensors": [{"type": "temperature"}, {"type": "pressure"}, {"type": "humidity"}]
        }
    ]

    runners = []
    device_instances = []

    try:
        for i, conf in enumerate(devices_config):
            port = BASE_PORT + i
            device = VirtualDevice(conf["name"], port, conf["sensors"])
            runner = await device.start()
            
            device_instances.append(device)
            runners.append(runner)
            
        logger.info(f"🚀 Simulation running with {len(device_instances)} devices.")
        logger.info("Press Ctrl+C to stop.")

        # Keep alive
        while True:
            await asyncio.sleep(3600)

    except asyncio.CancelledError:
        pass
    finally:
        logger.info("\nStopping simulation...")
        for d in device_instances:
            d.stop()
        for r in runners:
            await r.cleanup()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
