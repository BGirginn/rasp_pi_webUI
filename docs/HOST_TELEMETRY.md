# Connectivity and power telemetry

The agent's existing background collector stores these numeric measurements alongside
system metrics at its configured collection interval. Raw data,
rollups, SSE, `/api/telemetry/current` and the existing history/export endpoints use
the same metric names. Collection continues locally without internet access and
does not depend on the API being available. The deployed Pi currently uses a
30-second agent interval; the local configuration uses 2 seconds. Health probes
are cached for 5 seconds to share work between live requests and persistence.
The existing agent batching and degrade mode still apply. The API forwards these
readings; its local fallback reports running state but cannot supply agent sensors.

| Metric | Meaning |
|---|---|
| `host.net.internet_connected` | `1` if a fixed public HTTPS probe succeeds, otherwise `0` |
| `host.net.internet_latency_ms` | Successful HTTPS request duration, including DNS/TLS; absent when unreachable |
| `host.power.on` | `1` while the running Pi is observed; missing samples are unknown |
| `host.boot.timestamp` | OS boot time, Unix seconds; changes on reboot, not an API restart |
| `host.power.pmic.available` | `1` when valid PMIC readings are available; otherwise `0` |
| `host.power.input_voltage_v` | Actual `EXT5V_V` input reading, in volts; absent when unavailable |
| `host.power.pmic.<rail>.voltage_v` | Measured PMIC rail voltage, in volts |
| `host.power.pmic.<rail>.current_a` | Measured PMIC rail current, in amperes |

Internet probes use `https://www.gstatic.com/generate_204` (HTTP 204), then
`https://www.cloudflare.com/cdn-cgi/trace` (HTTP 200 with trace content) as fallback.
Redirects and captive login pages are not success. TLS certificates are verified.
The targets are fixed, carry no credentials, and cannot be supplied by API callers.
A firewall, DNS filtering or endpoint outage can make probes fail even when other
internet services remain accessible. No networking configuration is changed.

On supported Raspberry Pi hardware, `/usr/bin/vcgencmd pmic_read_adc` supplies
readings. Missing tools, unsupported hardware, permission errors and invalid output
produce an availability flag, never fabricated zero volts/amps. All valid rails are
stored separately. The UI shows input voltage, the live rail table, and history
for connectivity, running state, voltage and core/3V3 SYS rail currents.

**PMIC current is not total USB-C supply current.** USB devices and loads connected
directly to 5 V bypass these measurements. Currents at different rail voltages must
not be added to claim input current. See the
[Raspberry Pi power supply documentation](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#power-supply).
Total input current requires a separate physical sensor; none is assumed here.

**A powered-off Pi cannot write telemetry.** Missing records can also mean the API
stopped, storage failed or collection stalled. The UI breaks long gaps and reports
unavailable live observations as unknown instead of declaring power off. Exact
off/on events during downtime require an independently powered observer or UPS
sensor. Boot timestamps help distinguish a reboot from an API restart. Historical
state buckets contain the average of observed 0/1 samples (the connected/on sample
fraction), not continuous proof of uptime between samples.

Existing retention policies still apply: numeric measurements are sampled, not
unlimited waveform capture. No schema change or database reset is required.

## Reading the telemetry page

Power History separates input voltage (V, left axis) from the measured core and
3V3 SYS rail currents (mA, right axis). The rail table shows all available rails
in V and mA; calculated mW is voltage times current for that rail, not total
USB-C consumption. A dash means the corresponding measurement is unavailable.

Live history uses 30-second buckets, matching the agent's minimum collection
interval. Gaps longer than three buckets break the plotted line; a lone recorded
sample remains visible as a point. System Performance statistics show the latest,
average, minimum, maximum and available chart sample count for the selected range.
Disk history uses the canonical `disk.root.used_pct` metric. The agent also records
`host.net.rx_bytes` and `host.net.tx_bytes`, summing non-loopback interface counters.
These include virtual interfaces, so they are not physical-link-only traffic.
RX/TX history needs two counter samples; resets and extended gaps have no rate.
Older deployments did not persist these aggregate counters, so earlier ranges can
show no RX/TX history. Existing per-interface records are preserved.
