#!/bin/bash
# ==============================================================================
# Start the Complete Astra 5G Fabric (10 Switches, 15 Hosts)
#
# Usage:
#   sudo bash scripts/run_usecase.sh              # interactive: you get the mininet> prompt
#   sudo bash scripts/run_usecase.sh --detached   # background Mininet + automatic healthcheck
#
# Interactive mode (default):
#   1. Starts the Ryu OpenFlow 1.3 controller in the background (logs/ryu.log)
#   2. Applies the Linux-HTB QoS queues in the background once the switches exist
#   3. Runs Mininet in THIS terminal, so you get the mininet> prompt
#      (h5 ping -c 2 h2, links, dump, exit ...). Open a SECOND terminal for the
#      helper scripts (healthcheck.sh, test_*.sh, faults/inject.sh) and for
#      `tail -f logs/ryu.log`.
#   Typing `exit` at the prompt stops Mininet and the controller.
#
# Detached mode: Mininet runs in the background on a FIFO (no prompt) and the
# 12-point healthcheck runs automatically at the end.
# ==============================================================================
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RYU_BIN="${RYU_BIN:-$ROOT/.venv/bin/ryu-manager}"
MODE="cli"
[ "$1" = "--detached" ] && MODE="detached"
mkdir -p "$ROOT/logs"

echo "=== Cleaning up previous instances and stale OVS bridges ==="
sudo pkill -f '[r]yu-manager' || true
sudo pkill -f '[a]stra_5g_topo' || true
for s in s1 s2 s3 s4 s5 s6 s7 s8 s9 s10; do
  sudo ovs-vsctl del-br "$s" 2>/dev/null || true
done
sudo mn -c >/dev/null 2>&1

echo "== 1. Launching Ryu 5G SDN Controller =="
$RYU_BIN "$ROOT/src/astra_controller.py" > "$ROOT/logs/ryu.log" 2>&1 &
sleep 3

if [ "$MODE" = "detached" ]; then
  echo "== 2. Starting Mininet Topology in the background (10 Switches, 15 Hosts) =="
  rm -f "$ROOT/mn_fifo"
  mkfifo "$ROOT/mn_fifo"
  nohup sudo python3 "$ROOT/src/astra_5g_topo.py" < "$ROOT/mn_fifo" > "$ROOT/logs/mn.log" 2>&1 &
  ( exec 3>"$ROOT/mn_fifo"; sleep 86400 ) &
  sleep 8

  echo "== 3. Applying Linux-HTB QoS Queues =="
  sudo bash "$ROOT/src/astra_qos.sh" > "$ROOT/logs/qos.log" 2>&1 && echo "QoS Queues Active."

  echo "== 4. Running End-to-End Baseline Healthcheck =="
  sudo bash "$ROOT/scripts/healthcheck.sh"
  exit 0
fi

# ---------------------------- interactive mode ---------------------------------
echo "== 2. QoS queues will be applied automatically once the switches are up =="
(
  for _ in $(seq 90); do
    ip link show s10-eth1 >/dev/null 2>&1 && break
    sleep 1
  done
  sleep 3
  if sudo bash "$ROOT/src/astra_qos.sh" > "$ROOT/logs/qos.log" 2>&1; then
    echo ""; echo "[Astra] QoS queues active. Press Enter to refresh the mininet> prompt."
  else
    echo ""; echo "[Astra] QoS setup failed, see logs/qos.log"
  fi
) &

echo "== 3. Starting Mininet (10 Switches, 15 Hosts) - the mininet> prompt follows =="
echo "   Second terminal: sudo bash scripts/healthcheck.sh | tail -f logs/ryu.log"
echo ""
sudo python3 "$ROOT/src/astra_5g_topo.py" || true

echo "=== Mininet exited: stopping controller and cleaning up ==="
sudo pkill -f '[r]yu-manager' || true
sudo mn -c >/dev/null 2>&1 || true
