
import asyncio
import sys
import json
import logging

# Add agent directory to sys.path
sys.path.append("/opt/pi-control/agent")

try:
    from rpc.socket_server import SocketClient
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

async def test_rpc():
    print("Connecting to /run/pi-agent/agent.sock...")
    client = SocketClient("/run/pi-agent/agent.sock")
    
    try:
        await client.connect()
        print("Connected!")
        
        print("Calling network.wifi.scan...")
        result = await client.call("network.wifi.scan")
        
        # Result should be wrapped in {"result": ...} by server, 
        # but client.call unwraps it and returns the inner result.
        # But wait, pi-agent.py _handle_rpc returns {"result": result} or {"error": ...}
        # socket_server.py _process_request wraps that in JSON-RPC standard response.
        # client.call unwraps the "result" field of JSON-RPC response.
        # So 'result' variable here will contain `{"result": [...]}` from handler?
        # Let's see. logic in pi-agent.py: return {"result": result}
        # logic in socket_server.py: "result": result.get("result") 
        # So client.call returns the raw list of networks.
        
        print("RPC Call Successful.")
        if isinstance(result, list):
             print(f"Networks Found: {len(result)}")
             for net in result:
                 print(f" - {net.get('ssid')} ({net.get('signal_quality')}%)")
        elif isinstance(result, dict) and 'result' in result: # If unwrapped differently
             print(f"Networks Found: {len(result['result'])}")
        else:
             print(f"Unexpected result type: {type(result)}")
             print(result)

    except Exception as e:
        print(f"RPC Verification Failed: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(test_rpc())
