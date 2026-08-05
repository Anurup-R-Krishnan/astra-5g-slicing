#!/bin/bash
set -ex

echo "=== Cleaning up any old state ==="
sudo pkill -f '[r]yu-manager' || true
sudo pkill -f '[a]stra_5g_topo' || true
for s in s1 s2 s3 s4 s5 s6; do sudo ovs-vsctl del-br $s 2>/dev/null || true; done
sudo mn -c >/dev/null 2>&1

echo "=== 1. Starting RYU Controller ==="
source /home/anuruprkris/Project/ryu-env/bin/activate
ryu-manager astra_controller.py ryu.app.ofctl_rest > /tmp/ryu.log 2>&1 &
RYU_PID=$!
sleep 3

echo "=== 2. Starting Mininet Topology ==="
tail -f /dev/null | sudo python3 astra_5g_topo.py > /tmp/mn.log 2>&1 &
MN_PID=$!
sleep 15  # wait for STP to converge

echo "=== 3. Applying QoS Policies ==="
sudo bash astra_qos.sh

echo "=== 4. Running Performance Benchmark ==="
sudo /home/anuruprkris/Project/ryu-env/bin/python astra_perf.py

echo "=== Cleaning up ==="
sudo kill $MN_PID || true
sudo kill $RYU_PID || true
sudo pkill -f '[r]yu-manager' || true
sudo pkill -f '[a]stra_5g_topo' || true
for s in s1 s2 s3 s4 s5 s6; do sudo ovs-vsctl del-br $s 2>/dev/null || true; done
sudo mn -c >/dev/null 2>&1

echo "=== Lab Completed Successfully! ==="
