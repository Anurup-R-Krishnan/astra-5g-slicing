#!/usr/bin/env python3
"""
Astra Mobility 5G SDN Slicing Lab — Charts & Topology
Generates: topology diagram + performance comparison charts.
"""

import json
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import networkx as nx

OUT = '.'


def draw_topology():
    G = nx.Graph()
    ring = [('s1', 's2'), ('s2', 's3'), ('s3', 's4'), ('s4', 's1')]
    edge = [('s5', 's1'), ('s6', 's3')]
    hosts = [('h1', 's2'), ('h2', 's4'),
             ('h3', 's5'), ('h4', 's5'), ('h5', 's5'), ('h6', 's5'),
             ('h7', 's6'), ('h8', 's6'), ('h9', 's6')]

    pos = {'s1': (0, 0), 's2': (2, 0), 's3': (2, -2), 's4': (0, -2)}
    pos['s5'] = (0, 2)
    pos['s6'] = (2, -4)
    hpos = {
        'h1': (3, 0.6), 'h2': (-1, -2.6),
        'h3': (-1.2, 2.7), 'h4': (-0.6, 3.2), 'h5': (0.6, 3.2), 'h6': (1.2, 2.7),
        'h7': (1.2, -4.7), 'h8': (1.6, -5.2), 'h9': (2.4, -4.7)
    }
    pos.update(hpos)

    for a, b in ring + edge:
        G.add_edge(a, b)
    for h, sw in hosts:
        G.add_edge(h, sw)

    fig, ax = plt.subplots(figsize=(12, 8))
    nx.draw_networkx_nodes(G, pos, nodelist=['s1', 's2', 's3', 's4'],
                           node_color='#d35400', node_size=1500, ax=ax)
    nx.draw_networkx_nodes(G, pos, nodelist=['s5', 's6'],
                           node_color='#e67e22', node_size=1200, ax=ax)
    nx.draw_networkx_nodes(G, pos, nodelist=['h1', 'h2'],
                           node_color='#16a085', node_size=800, ax=ax)
    nx.draw_networkx_nodes(G, pos, nodelist=['h3', 'h4'],
                           node_color='#8e44ad', node_size=500, ax=ax)
    nx.draw_networkx_nodes(G, pos, nodelist=['h5', 'h6'],
                           node_color='#c0392b', node_size=500, ax=ax)
    nx.draw_networkx_nodes(G, pos, nodelist=['h7', 'h8', 'h9'],
                           node_color='#f39c12', node_size=500, ax=ax)

    nx.draw_networkx_edges(G, pos, edgelist=ring, width=4.0, edge_color='#2c3e50', ax=ax)
    nx.draw_networkx_edges(G, pos, edgelist=edge, width=2.5, edge_color='#7f8c8d', ax=ax)
    nx.draw_networkx_edges(G, pos, edgelist=[(h, sw) for h, sw in hosts],
                           width=1.0, edge_color='#bdc3c7', ax=ax)

    nx.draw_networkx_labels(G, pos, font_size=9, font_color='white', font_weight='bold', ax=ax)

    ax.text(0, 2.45, 'gNodeB-A (s5)', fontsize=11, ha='center', fontweight='bold')
    ax.text(2, -4.45, 'gNodeB-B (s6)', fontsize=11, ha='center', fontweight='bold')
    ax.text(1.05, 0.6, 'eMBB UPF (h1) [s2]', fontsize=10, color='#16a085', fontweight='bold')
    ax.text(-1.0, -2.9, 'URLLC UPF (h2) [s4]', fontsize=10, color='#16a085', fontweight='bold')

    legend = [
        ('#d35400', 'Core Ring Switch (s1-s4)'),
        ('#e67e22', 'Edge Aggregator Switch (s5, s6)'),
        ('#16a085', 'UPF Core Server (h1, h2)'),
        ('#8e44ad', 'eMBB Smartphone UE (h3, h4)'),
        ('#c0392b', 'URLLC Autonomous Car UE (h5, h6)'),
        ('#f39c12', 'mMTC IoT Sensor UE (h7-h9)'),
    ]
    for c, lbl in legend:
        ax.plot([], [], marker='o', ms=10, color=c, ls='', label=lbl)
    ax.legend(loc='lower left', fontsize=9, framealpha=0.9)

    ax.set_title('Astra Mobility 5G Core Fabric — SDN Slicing Topology\n'
                 '10 Mbps Core Ring Links | OpenFlow 1.3 | Ryu Controller', fontsize=13, fontweight='bold')
    ax.axis('off')
    plt.tight_layout()
    plt.savefig(OUT + '/astra_5g_topology.png', dpi=150)
    plt.close()
    print('wrote astra_5g_topology.png')


def draw_performance():
    json_path = '/tmp/astra_results.json' if os.path.exists('/tmp/astra_results.json') else 'astra_results.json'
    with open(json_path) as f:
        r = json.load(f)

    available_phases = [p for p in ['baseline', 'rate_limited', 'priority_qos', 'full_contention'] if p in r]
    phase_labels = {'baseline': 'No QoS', 'rate_limited': 'Rate-Limited', 'priority_qos': 'Priority QoS', 'full_contention': 'Full Contention'}
    phases = [phase_labels[p] for p in available_phases]

    def get_val(p, key_mean, key_simple, subkey=None):
        if key_mean in r[p]:
            return r[p][key_mean]
        elif key_simple in r[p]:
            val = r[p][key_simple]
            if subkey and isinstance(val, dict):
                return val.get(subkey, 0)
            return val
        return 0

    urllc_t = [get_val(p, 'urllc_t_mean', 'urllc_t') for p in available_phases]
    embb_t = [get_val(p, 'embb_t_mean', 'embb_t') for p in available_phases]
    urllc_l = [get_val(p, 'urllc_l_avg_mean', 'urllc_l', 'avg') for p in available_phases]
    urllc_j = [get_val(p, 'urllc_l_jitter_mean', 'urllc_l', 'jitter') for p in available_phases]

    colors = ['#bdc3c7', '#f39c12', '#27ae60', '#e74c3c'][:len(available_phases)]

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    ax = axes[0]
    x = list(range(len(phases)))
    w = 0.35
    ax.bar([i - w / 2 for i in x], urllc_t, width=w, label='URLLC', color='#c0392b')
    ax.bar([i + w / 2 for i in x], embb_t, width=w, label='eMBB', color='#8e44ad')
    ax.set_title('Slice Throughput (Mbps)', fontweight='bold')
    ax.set_xticks(x); ax.set_xticklabels(phases)
    ax.set_ylabel('Mbps'); ax.legend()
    for i, (u, e) in enumerate(zip(urllc_t, embb_t)):
        ax.text(i - w / 2, u + 0.1, f'{u:.1f}', ha='center', fontsize=9)
        ax.text(i + w / 2, e + 0.1, f'{e:.1f}', ha='center', fontsize=9)

    ax = axes[1]
    ax.bar(x, urllc_l, color=colors)
    ax.set_title('URLLC Avg Latency (ms)', fontweight='bold')
    ax.set_xticks(x); ax.set_xticklabels(phases)
    ax.set_ylabel('ms (log scale)')
    ax.set_yscale('log')
    for i, v in enumerate(urllc_l):
        ax.text(i, v * 1.15 if v > 0 else 1, f'{v:.0f}ms', ha='center', fontsize=10)

    if len(urllc_l) >= 3 and urllc_l[0] > 0 and urllc_l[2] > 0:
        ratio = urllc_l[0] / urllc_l[2]
        ax.text(0.5, 0.6, f'{ratio:.0f}x Improvement', transform=ax.transAxes, fontsize=16,
                color='#27ae60', fontweight='bold', ha='center',
                bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=4))

    ax = axes[2]
    ax.bar(x, urllc_j, color=colors)
    ax.set_title('URLLC Jitter (ms)', fontweight='bold')
    ax.set_xticks(x); ax.set_xticklabels(phases)
    ax.set_ylabel('ms')
    for i, v in enumerate(urllc_j):
        ax.text(i, v + 2, f'{v:.0f}ms', ha='center', fontsize=10)

    fig.suptitle('Astra Mobility 5G — QoS Impact on Slice Performance', fontsize=15, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    plt.savefig(OUT + '/astra_5g_performance.png', dpi=150)
    plt.close()
    print('wrote astra_5g_performance.png')


if __name__ == '__main__':
    draw_topology()
    draw_performance()
