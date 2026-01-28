
import asyncio
import logging
import sys
import os

# Add agent directory to sys.path
sys.path.append("/opt/pi-control/agent")

# Mock config
config = {"logging": {"level": "DEBUG"}}

try:
    from providers.network_provider import NetworkProvider
    import structlog
except ImportError as e:
    print(f"Import Error: {e}")
    sys.path.append("/Users/bgirginn/Desktop/rasp_pi_webUI/agent") # Fallback for local testing if paths differ
    from providers.network_provider import NetworkProvider
    import structlog

# Setup logging
structlog.configure(
    processors=[structlog.processors.JSONRenderer()],
    logger_factory=structlog.stdlib.LoggerFactory(),
)
logging.basicConfig(level=logging.DEBUG)

async def test_provider():
    print("Initializing NetworkProvider...")
    provider = NetworkProvider(config)
    await provider.start()
    
    print("Executing scan action via 'wlan0'...")
    # Matches ProviderManager logic
    result = await provider.execute_action("wlan0", "scan")
    
    print(f"Result Success: {result.success}")
    if result.success:
        networks = result.data.get("networks", [])
        print(f"Networks Found: {len(networks)}")
        for net in networks:
            print(f" - {net['ssid']} ({net['signal_quality']}%)")
    else:
        print(f"Error Message: {result.message}")
        print(f"Detailed Error: {result.error}")

if __name__ == "__main__":
    asyncio.run(test_provider())
