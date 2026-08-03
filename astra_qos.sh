#!/bin/bash
# ============================================
# Astra Mobility 5G Slice QoS Deployment
# Bottleneck: s1-eth1 (s1->s2) and s1-eth4 (s1->s4)
# ============================================

set -e
echo "=== Astra 5G Slice QoS Setup ==="

# The ring has two possible paths from s5 (gNodeB-A) to s4 (URLLC UPF):
#   Short: s5->s1->s4  (URLLC takes this)
#   Long:  s5->s1->s2->s3->s4  (eMBB takes this)
# We apply QoS on s1's uplinks to the ring.

PORT_SHORT="s1-eth2"   # s1 -> s4 (URLLC fast path)
PORT_LONG="s1-eth1"    # s1 -> s2 (eMBB load-balanced path)

# Clear old QoS
sudo ovs-vsctl clear port $PORT_SHORT qos 2>/dev/null || true
sudo ovs-vsctl clear port $PORT_LONG qos 2>/dev/null || true

# ============================================
# HTB Queues on SHORT path (s1->s4)
# Queue 0: URLLC - strict priority, 50% min guarantee
# Queue 1: mMTC   - best effort
# ============================================
echo "[1] Configuring SHORT path (s1->s4) for URLLC priority..."
sudo ovs-vsctl set port $PORT_SHORT qos=@newqos -- \
    --id=@newqos create QoS type=linux-htb \
    other-config:max-rate=10000000 \
    queues:0=@urllc queues:1=@mmtc -- \
    --id=@urllc create Queue other-config:min-rate=5000000 \
                             other-config:max-rate=10000000 \
                             other-config:priority=0 \
                             external-ids:description="URLLC_slice" -- \
    --id=@mmtc create Queue other-config:min-rate=500000 \
                            other-config:max-rate=2000000 \
                            other-config:priority=2 \
                            external-ids:description="mMTC_slice"

# ============================================
# HTB Queues on LONG path (s1->s2)
# Queue 0: eMBB - rate limited to prevent saturation
# Queue 1: mMTC - spillover
# ============================================
echo "[2] Configuring LONG path (s1->s2) for eMBB load-balancing..."
sudo ovs-vsctl set port $PORT_LONG qos=@newqos -- \
    --id=@newqos create QoS type=linux-htb \
    other-config:max-rate=10000000 \
    queues:0=@embb queues:1=@mmtc2 -- \
    --id=@embb create Queue other-config:min-rate=2000000 \
                            other-config:max-rate=4000000 \
                            other-config:priority=1 \
                            external-ids:description="eMBB_slice" -- \
    --id=@mmtc2 create Queue other-config:min-rate=500000 \
                             other-config:max-rate=1000000 \
                             other-config:priority=2 \
                             external-ids:description="mMTC_spillover"

# ============================================
# Meter: Hard rate limit on eMBB aggregate
# ============================================
echo "[3] Creating meter for eMBB hard cap..."
curl -s -X POST -d '{
    "dpid": 1,
    "flags": "KBPS",
    "meter_id": 100,
    "bands": [
        {"type": "DROP", "rate": 4000, "burst_size": 400}
    ]
}' http://localhost:8080/stats/meterentry/add

# ============================================
# Flow Rules with Queue Assignment
# ============================================

# --- URLLC (h5, h6 -> h2): Queue 0 on SHORT path, DSCP 46 (EF) ---
for IP in "10.0.0.5" "10.0.0.6"; do
curl -s -X POST -d "{
    \"dpid\": 1,
    \"table_id\": 0,
    \"priority\": 500,
    \"match\": {
        \"eth_type\": 2048,
        \"ipv4_src\": \"$IP\"
    },
    \"actions\": [
        {\"type\": \"SET_FIELD\", \"field\": \"ip_dscp\", \"value\": 46},
        {\"type\": \"SET_QUEUE\", \"queue_id\": 0},
        {\"type\": \"OUTPUT\", \"port\": 2}
    ]
}" http://localhost:8080/stats/flowentry/add
done

# --- eMBB (h3, h4 -> h1): Queue 0 on LONG path, meter 100, DSCP 34 (AF41) ---
# NOTE: ofctl_rest cannot parse OF1.3 'instructions' (meter) JSON, so we insert
#       the meter-bearing eMBB flows directly with ovs-ofctl.
for IP in "10.0.0.3" "10.0.0.4"; do
sudo ovs-ofctl -O OpenFlow13 add-flow s1 "priority=400,ip,nw_src=$IP actions=meter:100,set_field:34->ip_dscp,set_queue:0,output:1"
done

# --- mMTC (h7, h8, h9): Queue 1 on both paths, DSCP 0 ---
for IP in "10.0.0.7" "10.0.0.8" "10.0.0.9"; do
curl -s -X POST -d "{
    \"dpid\": 1,
    \"table_id\": 0,
    \"priority\": 300,
    \"match\": {
        \"eth_type\": 2048,
        \"ipv4_src\": \"$IP\"
    },
    \"actions\": [
        {\"type\": \"SET_QUEUE\", \"queue_id\": 1},
        {\"type\": \"OUTPUT\", \"port\": \"NORMAL\"}
    ]
}" http://localhost:8080/stats/flowentry/add
done

echo "[4] QoS deployment complete."

# Verification
echo ""
echo "=== Verification ==="
echo "--- Queues ---"
sudo ovs-vsctl list Queue
echo ""
echo "--- Meters ---"
curl -s http://localhost:8080/stats/meter/1 | python3 -m json.tool
echo ""
echo "--- Flows on s1 ---"
curl -s http://localhost:8080/stats/flow/1 | python3 -m json.tool | head -80
