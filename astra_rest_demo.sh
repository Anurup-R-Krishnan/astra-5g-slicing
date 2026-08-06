#!/bin/bash
set -e

echo "=== Astra Mobility 5G REST API Demonstration ==="
echo ""

echo "1. Checking registered switches:"
curl -s http://localhost:8080/stats/switches | jq .
echo ""

echo "2. Emergency Reroute: Rerouting h3 (eMBB) via SHORT path on s1"
# Priority 200 flow on s1 to push 10.0.0.3 (h3) out of port 2 (s1-eth2 / short path)
curl -s -X POST -d '{
    "dpid": 1,
    "cookie": 100,
    "priority": 200,
    "match":{
        "eth_type": 2048,
        "ipv4_src": "10.0.0.3"
    },
    "actions":[
        {
            "type": "OUTPUT",
            "port": 2
        }
    ]
}' http://localhost:8080/stats/flowentry/add
echo "Emergency reroute rule added."
echo ""

echo "3. Security Block: Dropping traffic from h4 (10.0.0.4) to h2 (10.0.0.2) on s5"
# Priority 500 flow on s5 to drop traffic matching nw_src=10.0.0.4, nw_dst=10.0.0.2
curl -s -X POST -d '{
    "dpid": 5,
    "cookie": 101,
    "priority": 500,
    "match":{
        "eth_type": 2048,
        "ipv4_src": "10.0.0.4",
        "ipv4_dst": "10.0.0.2"
    },
    "actions":[]
}' http://localhost:8080/stats/flowentry/add
echo "Security block rule added."
echo ""

echo "4. Verifying flows on s1 (showing the reroute rule):"
sudo ovs-ofctl -O OpenFlow13 dump-flows s1 | grep "nw_src=10.0.0.3"
echo ""

echo "5. Verifying flows on s5 (showing the drop rule):"
sudo ovs-ofctl -O OpenFlow13 dump-flows s5 | grep "nw_src=10.0.0.4"
echo ""

echo "6. Cleaning up demonstration rules..."
curl -s -X POST -d '{
    "dpid": 1,
    "cookie": 100
}' http://localhost:8080/stats/flowentry/delete_strict

curl -s -X POST -d '{
    "dpid": 5,
    "cookie": 101
}' http://localhost:8080/stats/flowentry/delete_strict

echo "Clean up complete."
echo "=== Demonstration Finished ==="
