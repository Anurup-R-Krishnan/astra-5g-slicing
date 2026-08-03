# Astra Mobility 5G SDN Slicing Lab

Mininet + Open vSwitch + RYU network slicing lab emulating a 5G core fabric.
Three slices (eMBB / URLLC / mMTC) share one physical ring with slice-specific
routing, queuing, and rate-limiting.

```
        gNodeB-A (s5)                    gNodeB-B (s6)
   h3 h4 (eMBB)  h5 h6 (URLLC)      h7 h8 h9 (mMTC)
         \      |      /                  \  |  /
          s5 ----|---- s6
           |           |
   h1 eMBB-UPF--s2--s3--s4--URLLC-UPF h2
              \  |  /   core ring
               s1  (ingress / QoS enforcement point)
```

- **Core ring**: s1-s2-s3-s4 (10 Mbps links, `delay=2ms`)
- **Edge aggregation**: s5 (gNodeB-A) -> s1, s6 (gNodeB-B) -> s3
- **Paths from s5**: SHORT `s5->s1->s4` (URLLC, via `s1-eth2`), LONG `s5->s1->s2->s3->s4` (eMBB, via `s1-eth1`)
- **Hosts / slices**: h3,h4 -> eMBB; h5,h6 -> URLLC; h7,h8,h9 -> mMTC; h1 = eMBB UPF (s2); h2 = URLLC UPF (s4)

## Prerequisites (Arch Linux)

| Package | Purpose | Install |
|---|---|---|
| openvswitch | OVS switch 3.7+ | `pacman -S openvswitch` |
| mininet | network emulator | `pacman -S mininet` |
| iperf3 | traffic generation | `pacman -S iperf3` |
| wireshark-cli | tshark DSCP analysis | `pacman -S wireshark-cli` |
| python-ryu | RYU 4.34 controller | `pip install ryu` (venv, Python 3.9) |
| networkx / matplotlib | charts | `pip install networkx matplotlib` |

RYU is installed in a virtualenv (`/home/anuruprkris/Project/ryu-env`, Python 3.9.25).
Mininet lives in system python (`/usr/bin/python`); it is NOT in the venv.

### Critical environment gotchas

1. **Broken `env` wrapper**: `/home/anuruprkris/.local/bin/env` shadows coreutils
   `env` and swallows arguments, which breaks Mininet's host shells. Always invoke
   Mininet through `/usr/bin/env` explicitly:

   ```
   /usr/bin/env PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin /usr/bin/python astra_5g_topo.py
   ```

2. **STP**: the ring is a switching loop. If it floods (watch `/tmp/ryu.log` for a
   packet-in storm), enable STP on every bridge:
   ```
   for s in s1 s2 s3 s4 s5 s6; do ovs-vsctl set bridge $s stp_enable=true; done
   ```
   (In this lab STP blocks `s3-eth1`; s1 stays fully forwarding.)

3. **Port map**: s1 has only THREE links — `s1-eth1` (ofport 1, ->s2, LONG/eMBB path),
   `s1-eth2` (ofport 2, ->s4, SHORT/URLLC path), `s1-eth3` (->s5). Earlier lab docs
   said `s1-eth4`; the scripts here use the correct ports.

4. **RYU ofctl_rest cannot parse OF1.3 `instructions`/`meter` JSON** (only reads
   `actions`). Meter-bearing eMBB flows must be inserted with `ovs-ofctl`:
   ```
   sudo ovs-ofctl -O OpenFlow13 add-flow s1 "priority=400,ip,nw_src=10.0.0.3 actions=meter:100,set_field:34->ip_dscp,set_queue:0,output:1"
   ```

5. **Commands inside host namespaces**: use `mnexec -a <pid> -- <cmd>` where pid =
   `pgrep -f 'mininet:hN'`. The Mininet CLI FIFO is flaky for this.

## Files

| File | Role |
|---|---|
| `astra_5g_topo.py` | Mininet topology (6 switches, 9 hosts, 10 Mbps ring). Run with system python. |
| `astra_controller.py` | RYU app: table-miss, ARP flood, MAC learning, slice-aware reactive priorities. |
| `astra_qos.sh` | Full QoS deployment: HTB queues, meter 100, DSCP/set-queue flows. |
| `astra_monitor.py` | Captures `s1-eth2`/`s1-eth1` with tcpdump, DSCP analysis with tshark, OVS/RYU stats. |
| `astra_perf.py` | 3-phase benchmark (baseline / rate-limited / priority QoS) via host namespaces. |
| `astra_charts.py` | Generates topology + performance PNGs. |

## Running the lab

All commands run from `/home/anuruprkris/Project/sdn` as root.

### 1. Start the RYU controller (port 6653, REST on 8080)

```
source ../ryu-env/bin/activate
setsid nohup ryu-manager --verbose astra_controller.py ryu.app.ofctl_rest \
  > /tmp/ryu.log 2>&1 < /dev/null & disown
```

Verify: `curl -s http://localhost:8080/stats/switches` — empty until topology joins.

### 2. Start Mininet (detached, FIFO-driven CLI)

```
rm -f /tmp/mn_fifo && mkfifo /tmp/mn_fifo
setsid nohup /usr/bin/env PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  /usr/bin/python astra_5g_topo.py < /tmp/mn_fifo > /tmp/mn.log 2>&1 & disown
setsid bash -c 'exec 3>/tmp/mn_fifo; sleep 7200' >/dev/null 2>&1 & disown   # keep FIFO open
```

Wait ~20s, then confirm all 6 switches registered:
```
curl -s http://localhost:8080/stats/switches        # expect [6,2,3,1,4,5]
grep 'Switch.*up' /tmp/ryu.log
```

Interactive CLI (optional): `echo 'pingall' > /tmp/mn_fifo` and read `/tmp/mn.log`.

### 3. Deploy slice QoS

```
bash astra_qos.sh
```

Deploys:
- HTB queues on `s1-eth2` (URLLC q0 min 5M/max 10M/prio 0, mMTC q1) and `s1-eth1` (eMBB q0 min 2M/max 4M/prio 1, mMTC spillover q1)
- meter 100 = 4 Mbps DROP (eMBB hard cap)
- Flows on s1:
  - prio 500 URLLC (10.0.0.5/.6) -> `set_field:46->ip_dscp`, `set_queue:0`, out 2 (SHORT path)
  - prio 400 eMBB (10.0.0.3/.4) -> `meter:100`, `set_field:34->ip_dscp`, `set_queue:0`, out 1 (LONG path)
  - prio 300 mMTC (10.0.0.7/8/9) -> `set_queue:1`, `NORMAL`

Verify:
```
ovs-ofctl -O OpenFlow13 dump-flows s1 | grep nw_src
ovs-ofctl -O OpenFlow13 dump-meters s1
curl -s http://localhost:8080/stats/flow/1
```

### 4. Monitor slice separation (tcpdump + tshark)

Generate mixed traffic first (e.g. `echo 'xterm h5' >/tmp/mn_fifo` or use perf below),
then:
```
source ../ryu-env/bin/activate
python astra_monitor.py        # 30s captures -> DSCP counts per path
```

Expected: SHORT path dominated by DSCP 46, LONG path by DSCP 34.

### 5. Run the performance benchmark

```
source ../ryu-env/bin/activate
python astra_perf.py
```

Three phases (each ~45s): **Baseline** (no QoS), **Rate-limited** (meter 100 only),
**Priority QoS** (full `astra_qos.sh`). Results in `/tmp/astra_results.json` and on
stdout. iperf3 saturator runs h4->h1 (port 5003/5004) while URLLC/eMBB are measured
on ports 5001/5002.

### 6. Charts

```
source ../ryu-env/bin/activate
python astra_charts.py
```

Writes `astra_5g_topology.png` and `astra_5g_performance.png` (requires a completed
`/tmp/astra_results.json`).

## REST API extras (demonstrated in lab)

- **Emergency reroute**: redirect all of h3 to the short path with priority 200:
  ```
  curl -s -X POST -d '{"dpid":1,"table_id":0,"priority":200,"match":{"eth_type":2048,"ipv4_src":"10.0.0.3"},"actions":[{"type":"OUTPUT","port":4}]}' http://localhost:8080/stats/flowentry/add
  ```
- **Security block**: drop h4 -> h2 at s5 with priority 500:
  ```
  curl -s -X POST -d '{"dpid":5,"table_id":0,"priority":500,"match":{"eth_type":2048,"ipv4_src":"10.0.0.4","ipv4_dst":"10.0.0.2"},"actions":[]}' http://localhost:8080/stats/flowentry/add
  ```
- Delete a flow: same body to `/stats/flowentry/delete_strict` (or `ovs-ofctl -O OpenFlow13 del-flows s1 priority=N`).

## Teardown

```
pkill -f '[r]yu-manager'
pkill -f '[a]stra_5g_topo'
pkill -f '[s]leep 7200'
for s in s1 s2 s3 s4 s5 s6; do ovs-vsctl del-br $s; done
```

## Observed results (reference)

| Metric | Baseline | Rate-limited | Priority QoS |
|---|---|---|---|
| URLLC throughput | 1.4 Mbps | 8.3 Mbps | 5.4 Mbps |
| URLLC avg latency | 2134 ms | 118 ms | 52 ms |
| URLLC jitter | 237 ms | — | 109 ms |
| eMBB throughput | 9.5 Mbps | 2.6 Mbps | 3.3 Mbps |

URLLC latency improved ~41x. DSCP monitoring confirmed zero cross-contamination
between slices on the shared ring.
