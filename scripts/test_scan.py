
import asyncio
import subprocess

async def scan():
    print("Starting scan...")
    cmd = ["nmcli", "-t", "-f", "SSID,BSSID,SIGNAL,BARS,SECURITY,CHAN,FREQ", "device", "wifi", "list"]
    
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    
    if proc.returncode != 0:
        print(f"Error: {stderr.decode()}")
        return

    output = stdout.decode("utf-8")
    print(f"Raw Output:\n---\n{output}\n---")
    
    for line in output.split("\n"):
        if not line.strip(): continue
        clean_line = line.replace("\\:", "__COLON__")
        parts = clean_line.split(":")
        if len(parts) < 7:
            print(f"Skipping malformed line: {line}")
            continue
        print(f"Parsed: SSID='{parts[0]}' SIGNAL={parts[2]}")

if __name__ == "__main__":
    asyncio.run(scan())
