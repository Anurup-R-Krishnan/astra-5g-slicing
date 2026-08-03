#!/usr/bin/env python3
"""
Astra Mobility 5G Performance Test
Before/after QoS: throughput, latency, jitter per slice.
Commands are executed inside Mininet host namespaces via mnexec.
"""

import subprocess
import json
import time
import statistics
import os


def host_pid(host):
    try:
        out = subprocess.run(['pgrep', '-f', 'mininet:' + host],
                             capture_output=True, text=True).stdout.strip()
        return out.split()[0] if out else None
    except Exception:
        return None


def host_cmd(host, *args):
    """Run a command inside a Mininet host's network namespace."""
    pid = host_pid(host)
    if not pid:
        return subprocess.run(args, capture_output=True, text=True)
    return subprocess.run(['mnexec', '-a', pid, '--'] + list(args),
                          capture_output=True, text=True, timeout=120)


class AstraPerfTest:
    def __init__(self):
        self.results = {
            'baseline': {},
            'rate_limited': {},
            'priority_qos': {}
        }

    def iperf3(self, client_host, server_host, port, duration=10, bandwidth='100M'):
        cmd = ['iperf3', '-c', '10.0.0.' + server_host.strip('h'),
               '-p', str(port), '-t', str(duration), '-J']
        if bandwidth:
            cmd.extend(['-b', bandwidth])
        try:
            r = host_cmd(client_host, *cmd)
            d = json.loads(r.stdout)
            return {
                'mbps': d['end']['sum_received']['bits_per_second'] / 1e6,
                'retrans': d['end']['sum_sent'].get('retransmits', 0)
            }
        except:
            return {'mbps': 0, 'retrans': 0}

    def ping(self, from_host, target, count=20):
        cmd = ['ping', '-c', str(count), '-i', '0.2', target]
        try:
            r = host_cmd(from_host, *cmd)
            latencies = []
            for line in r.stdout.split('\n'):
                if 'time=' in line:
                    latencies.append(float(line.split('time=')[1].split(' ')[0]))
            if len(latencies) >= 2:
                return {
                    'avg': statistics.mean(latencies),
                    'jitter': statistics.stdev(latencies),
                    'min': min(latencies),
                    'max': max(latencies)
                }
            return {'avg': 0, 'jitter': 0, 'min': 0, 'max': 0}
        except:
            return {'avg': 0, 'jitter': 0, 'min': 0, 'max': 0}

    def start_servers(self):
        # measurement ports 5001/5002 + dedicated saturator ports 5003/5004
        for host, port in [('h1', 5001), ('h2', 5002),
                           ('h1', 5003), ('h2', 5004)]:
            subprocess.Popen(['mnexec', '-a', host_pid(host), '--', 'iperf3', '-s',
                              '-p', str(port), '-D'],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)

    def stop_servers(self):
        subprocess.run(['pkill', '-f', 'iperf3 -s'])
        time.sleep(1)

    def qos_off(self):
        """Remove QoS flows, meter, queues (keeps base table-miss/ARP flows)."""
        print("  [qos_off] Tearing down QoS...")
        for prio in (500, 400, 300):
            subprocess.run(['sudo', 'ovs-ofctl', '-O', 'OpenFlow13', 'del-flows',
                            's1', 'priority=%d' % prio],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['curl', '-s', '-X', 'POST', '-d',
                        '{"dpid":1,"meter_id":100}',
                        'http://localhost:8080/stats/meterentry/delete'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for port in ('s1-eth1', 's1-eth2'):
            subprocess.run(['sudo', 'ovs-vsctl', 'clear', 'port', port, 'qos'],
                           stdout=subprocess.DEVNULL)
        time.sleep(1)

    def qos_on(self):
        """Re-deploy full slice QoS via astra_qos.sh."""
        print("  [qos_on] Deploying slice QoS...")
        subprocess.run(['bash', os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                             'astra_qos.sh')],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)

    def saturate(self, client_host, server_ip, port, bandwidth, duration=25):
        subprocess.Popen(['mnexec', '-a', host_pid(client_host), '--', 'iperf3',
                          '-c', server_ip, '-p', str(port), '-t', str(duration),
                          '-b', bandwidth],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def phase_baseline(self):
        print("\n" + "=" * 70)
        print("PHASE 1: BASELINE (No QoS — ring treats all traffic equally)")
        print("=" * 70)
        self.qos_off()
        self.start_servers()

        # Saturate the ring with eMBB, then measure URLLC
        print("\n  [Step 1] Saturating ring with eMBB (h4->h1 @ 80M)...")
        self.saturate('h4', '10.0.0.1', 5003, '80M')
        time.sleep(3)

        print("  [Step 2] Measuring URLLC (h5->h2) while ring is saturated...")
        r_urllc = self.iperf3('h5', 'h2', 5002, duration=10, bandwidth='20M')
        l_urllc = self.ping('h5', '10.0.0.2')

        print("  [Step 3] Measuring eMBB (h3->h1) throughput...")
        r_embb = self.iperf3('h3', 'h1', 5001, duration=10, bandwidth='80M')

        print(f"\n  URLLC (Car):  {r_urllc['mbps']:.1f} Mbps | Latency: {l_urllc['avg']:.2f}ms, Jitter: {l_urllc['jitter']:.2f}ms")
        print(f"  eMBB (Phone): {r_embb['mbps']:.1f} Mbps")

        self.results['baseline'] = {
            'urllc_t': r_urllc['mbps'], 'urllc_l': l_urllc,
            'embb_t': r_embb['mbps']
        }
        self.stop_servers()
        time.sleep(2)

    def phase_rate_limit(self):
        print("\n" + "=" * 70)
        print("PHASE 2: RATE LIMITING (eMBB hard-capped at 4 Mbps)")
        print("=" * 70)

        # Hard-cap eMBB with meter-based drop flows on the LONG path
        self.qos_off()
        subprocess.run(['curl', '-s', '-X', 'POST', '-d',
                        '{"dpid":1,"flags":"KBPS","meter_id":100,"bands":'
                        '[{"type":"DROP","rate":4000,"burst_size":400}]}',
                        'http://localhost:8080/stats/meterentry/add'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for ip in ('10.0.0.3', '10.0.0.4'):
            subprocess.run(['sudo', 'ovs-ofctl', '-O', 'OpenFlow13', 'add-flow',
                            's1', 'priority=400,ip,nw_src=%s actions=meter:100,output:1' % ip],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        self.start_servers()
        self.saturate('h4', '10.0.0.1', 5003, '80M')
        time.sleep(3)

        r_urllc = self.iperf3('h5', 'h2', 5002, duration=10, bandwidth='20M')
        l_urllc = self.ping('h5', '10.0.0.2')
        r_embb = self.iperf3('h3', 'h1', 5001, duration=10, bandwidth='80M')

        print(f"\n  URLLC (Car):  {r_urllc['mbps']:.1f} Mbps | Latency: {l_urllc['avg']:.2f}ms")
        print(f"  eMBB (Phone): {r_embb['mbps']:.1f} Mbps")

        self.results['rate_limited'] = {
            'urllc_t': r_urllc['mbps'], 'urllc_l': l_urllc,
            'embb_t': r_embb['mbps']
        }
        self.stop_servers()
        time.sleep(2)

    def phase_priority_qos(self):
        print("\n" + "=" * 70)
        print("PHASE 3: PRIORITY QUEUING (URLLC short path + priority queue)")
        print("=" * 70)
        print("Deploying QoS...")
        self.qos_on()
        self.start_servers()

        # eMBB on LONG path (s1->s2), URLLC on SHORT path (s1->s4)
        print("\n  [Step 1] eMBB saturating LONG path (h4->h1 @ 80M)...")
        self.saturate('h4', '10.0.0.1', 5003, '80M')
        time.sleep(3)

        print("  [Step 2] URLLC on SHORT path (h5->h2 @ 20M)...")
        r_urllc = self.iperf3('h5', 'h2', 5002, duration=10, bandwidth='20M')
        l_urllc = self.ping('h5', '10.0.0.2')

        print("  [Step 3] eMBB throughput on LONG path...")
        r_embb = self.iperf3('h3', 'h1', 5001, duration=10, bandwidth='80M')

        print(f"\n  URLLC (Car):  {r_urllc['mbps']:.1f} Mbps | Latency: {l_urllc['avg']:.2f}ms, Jitter: {l_urllc['jitter']:.2f}ms")
        print(f"  eMBB (Phone): {r_embb['mbps']:.1f} Mbps")

        self.results['priority_qos'] = {
            'urllc_t': r_urllc['mbps'], 'urllc_l': l_urllc,
            'embb_t': r_embb['mbps']
        }
        self.stop_servers()

    def report(self):
        print("\n" + "=" * 70)
        print("ASTRA MOBILITY 5G — FINAL PERFORMANCE REPORT")
        print("=" * 70)

        print("\n{:<22} {:>12} {:>14} {:>14}".format(
            "Metric", "Baseline", "Rate-Limited", "Priority QoS"))
        print("-" * 70)

        for slice_name, key in [('URLLC (Car)', 'urllc_t'), ('eMBB (Phone)', 'embb_t')]:
            b = self.results['baseline'][key]
            l = self.results['rate_limited'][key]
            p = self.results['priority_qos'][key]
            print(f"{slice_name} Throughput   {b:>10.1f}   {l:>12.1f}   {p:>12.1f}")

        print("-" * 70)

        for slice_name, key in [('URLLC (Car)', 'urllc_l')]:
            b = self.results['baseline'][key]['avg']
            l = self.results['rate_limited'][key]['avg']
            p = self.results['priority_qos'][key]['avg']
            print(f"{slice_name} Latency      {b:>10.2f}   {l:>12.2f}   {p:>12.2f}")

        print("-" * 70)

        for slice_name, key in [('URLLC (Car)', 'urllc_l')]:
            b = self.results['baseline'][key]['jitter']
            l = self.results['rate_limited'][key]['jitter']
            p = self.results['priority_qos'][key]['jitter']
            print(f"{slice_name} Jitter       {b:>10.2f}   {l:>12.2f}   {p:>12.2f}")

        print("=" * 70)

        with open('/tmp/astra_results.json', 'w') as f:
            json.dump(self.results, f, indent=2)
        print("\nResults saved to /tmp/astra_results.json")


if __name__ == '__main__':
    t = AstraPerfTest()
    t.phase_baseline()
    t.phase_rate_limit()
    t.phase_priority_qos()
    t.report()
