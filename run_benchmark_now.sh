sudo pkill -f ryu-manager || true
sudo pkill -f mininet || true
sudo mn -c >/dev/null 2>&1

source /home/cootot/ryu-env/bin/activate
nohup ryu-manager astra_controller.py ryu.app.ofctl_rest > ryu_bench.log 2>&1 &
sleep 5

nohup sudo python3 astra_5g_topo.py > mn_bench.log 2>&1 &
sleep 45

# Ping hack to populate ARP and MAC tables before tests
for host in h1 h2 h3 h4 h5 h6 h7 h8 h9; do
    pid=$(pgrep -f "mininet:$host" | head -n 1)
    if [ -n "$pid" ]; then
        for target in 10.0.0.1 10.0.0.2 10.0.0.3 10.0.0.4 10.0.0.5 10.0.0.6 10.0.0.7 10.0.0.8 10.0.0.9; do
            sudo mnexec -a $pid ping -c 1 -W 1 $target >/dev/null 2>&1
        done
    fi
done

# Needs to run as root because it executes mnexec
sudo /home/cootot/ryu-env/bin/python astra_perf.py

sudo pkill -f ryu-manager || true
sudo pkill -f mininet || true
sudo mn -c >/dev/null 2>&1
