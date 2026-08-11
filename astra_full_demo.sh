#!/bin/bash
# ============================================================
# Astra Mobility 5G SDN Slicing Lab — One-Shot End-to-End Demo
#
# Runs the complete pipeline in order:
#   1. Clean old state
#   2. Start RYU controller (port 6653, REST 8080)
#   3. Start Mininet topology (STP, s1 root)
#   4. Wait for STP convergence
#   5. Warm the MAC cache (pingAll workaround)
#   6. Deploy slice QoS (HTB queues + meter + DSCP flows)
#   7. DSCP isolation monitor (tcpdump both paths + tshark)
#   8. 4-phase performance benchmark (before/after QoS)
#   9. Generate charts
#  10. REST API demo (emergency reroute + security block)
#  11. Print summary
#
# Usage:  sudo bash astra_full_demo.sh
# Output: ryu.log, mn.log, astra_short_path.pcap, astra_long_path.pcap,
#         astra_monitor_output.txt, astra_results.json, *.png
# ============================================================

set -ex
cd "$(dirname "$0")"
PROJ_DIR="$(pwd)"
RYU_ENV="/home/anuruprkris/Project/ryu-env"
STEP=0

step() { STEP=$((STEP+1)); echo; echo "===== [$STEP] $1 ====="; echo; }

# ------------------------------------------------------------
step "Cleaning up old state"
sudo pkill -f '[r]yu-manager' || true
sudo pkill -f '[a]stra_5g_topo' || true
for s in s1 s2 s3 s4 s5 s6; do sudo ovs-vsctl del-br $s 2>/dev/null || true; done
sudo mn -c >/dev/null 2>&1 || true

# ------------------------------------------------------------
step "Starting RYU controller"
source "$RYU_ENV/bin/activate"
setsid nohup ryu-manager --verbose astra_controller.py ryu.app.ofctl_rest > ryu.log 2>&1 < /dev/null & disown
sleep 3

# ------------------------------------------------------------
step "Starting Mininet topology (ring + STP, s1 root)"
rm -f mn_fifo && mkfifo mn_fifo
setsid nohup python3 astra_5g_topo.py < mn_fifo > mn.log 2>&1 & disown
setsid bash -c 'exec 3>mn_fifo; sleep 7200' >/dev/null 2>&1 & disown
echo "Waiting 20s for topology + STP convergence..."
sleep 20

# ------------------------------------------------------------
step "Warming MAC cache (so iperf/ping don't stall on ARP)"
for src in h3 h4 h5 h6 h7 h8 h9; do
  pid=$(pgrep -f "mininet:$src" | head -1)
  for dst in 10.0.0.1 10.0.0.2; do
    sudo mnexec -a "$pid" ping -c 1 -W 1 "$dst" >/dev/null 2>&1 || true
  done
done

# ------------------------------------------------------------
step "Deploying slice QoS (HTB queues + meter 100 + DSCP flows)"
bash astra_qos.sh

# ------------------------------------------------------------
step "Running DSCP isolation monitor (30s capture on both paths)"
source "$RYU_ENV/bin/activate"
python astra_monitor.py | tee astra_monitor_output.txt

# ------------------------------------------------------------
step "Running 4-phase performance benchmark (before/after QoS)"
sudo "$RYU_ENV/bin/python" astra_perf.py

# ------------------------------------------------------------
step "Generating charts"
"$RYU_ENV/bin/python" astra_charts.py || echo "[WARN] chart generation skipped"

# ------------------------------------------------------------
step "REST API demo (emergency reroute + security block)"
bash astra_rest_demo.sh || echo "[WARN] REST demo skipped (controller REST may need a moment)"

# ------------------------------------------------------------
step "Summary"
echo "=== Astra Lab Complete ==="
echo "  Monitor  : $PROJ_DIR/astra_monitor_output.txt"
echo "  Results  : $PROJ_DIR/astra_results.json"
echo "  Charts   : $PROJ_DIR/astra_5g_performance.png"
echo "  Captures : $PROJ_DIR/astra_short_path.pcap, astra_long_path.pcap"
echo "  Logs     : $PROJ_DIR/ryu.log, $PROJ_DIR/mn.log"
echo ""
echo "Quick verification:"
sudo ovs-ofctl -O OpenFlow13 dump-flows s1 | grep nw_src | head -6 || true
