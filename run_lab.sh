#!/bin/bash
set -ex

echo "=== Cleaning up any old state ==="
sudo pkill -f '[r]yu-manager' || true
sudo pkill -f '[a]stra_5g_topo' || true
for s in s1 s2 s3 s4 s5 s6; do sudo ovs-vsctl del-br $s 2>/dev/null || true; done
sudo mn -c >/dev/null 2>&1

echo "=== 1. Starting RYU Controller ==="
source /home/cootot/ryu-env/bin/activate
ryu-manager astra_controller.py ryu.app.ofctl_rest > /tmp/ryu.log 2>&1 &
RYU_PID=$!
sleep 3

echo "=== 2. Starting Mininet Topology ==="
tail -f /dev/null | sudo python3 astra_5g_topo.py > /tmp/mn.log 2>&1 &
MN_PID=$!
sleep 15  # wait for STP to converge

echo "=== 3. Applying QoS Policies ==="
#sudo bash astra_qos.sh

echo "=== 3.5. Populating MAC cache (pingAll workaround) ==="
for src in h3 h4 h5 h6 h7 h8 h9; do
  pid=$(pgrep -f "mininet:$src")
  for dst in 10.0.0.1 10.0.0.2; do
    sudo mnexec -a $pid ping -c 1 -W 1 $dst >/dev/null 2>&1 || true
  done
done
echo "=== 4. Running Performance Benchmark ==="
sudo /home/cootot/ryu-env/bin/python astra_perf.py

# Skipping teardown so the environment stays up for T1.8 and Phase 2.
echo "=== Lab Completed Successfully! ==="
