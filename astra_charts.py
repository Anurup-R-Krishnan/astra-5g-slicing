#!/usr/bin/env python3
"""
Astra Mobility 5G SDN Slicing Lab — Charts & Topology
Generates: topology diagram + performance comparison charts.
"""

import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import networkx as nx

OUT = '/home/anuruprkris/Project/sdn'


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
        'h3': (-1.1, 2.7), 'h4': (-0.6, 3.2), 'h5': (0.6, 3.2), 'h6': (1.1, 2.7),
        'h7': (1.1, -4.7), 'h8': (1.6, -5.2), 'h9': (2.4, -4.7)
    }
    pos.update(hpos)

    for a, b in ring + edge:
        G.add_edge(a, b)
    for h, sw in hosts:
        G.add_edge(h, sw)

    fig, ax = plt.subplots(figsize=(13, 9))
    nx.draw_networkx_nodes(G, pos, nodelist=['s1', 's2', 's3', 's4'],
                           node_color='#d35400', node_size=1500, ax=ax)
    nx.draw_networkx_nodes(G, pos, nodelist=['s5', 's6'],
                           node_color='#e67e22', node_size=1200, ax=ax)
    nx.draw_networkx_nodes(G, pos, nodelist=['h1', 'h2'],
                           node_color='#16a085', node_size=800, ax=ax)
    nx.draw_networkx_nodes(G, pos, nodelist=['h3', 'h4', 'h5', 'h6', 'h7', 'h8', 'h9'],
                           node_color='#8e44ad', node_size=500, ax=ax)

    nx.draw_networkx_edges(G, pos, edgelist=ring, width=4.0, edge_color='#2c3e50', ax=ax)
    nx.draw_networkx_edges(G, pos, edgelist=edge, width=2.5, edge_color='#7f8c8d', ax=ax)
    nx.draw_networkx_edges(G, pos, edgelist=[(h, sw) for h, sw in hosts],
                           width=1.0, edge_color='#bdc3c7', ax=ax)

    nx.draw_networkx_labels(G, pos, font_size=9, font_color='white', font_weight='bold', ax=ax)

    slice_colors = {'h3': '#8e44ad', 'h4': '#8e44ad', 'h5': '#c0392b', 'h6': '#c0392b',
                    'h7': '#f39c12', 'h8': '#f39c12', 'h9': '#f39c12'}
    for h, (x, y) in hpos.items():
        if h not in slice_colors:
            continue
        ax.plot(x + 0.18, y + 0.15, marker='o', color=slice_colors[h], markersize=8, ls='')

    ax.text(0, 2.42, 'gNodeB-A', fontsize=10, ha='center', style='italic')
    ax.text(2, -4.42, 'gNodeB-B', fontsize=10, ha='center', style='italic')
    ax.text(1.05, 0.6, 'eMBB UPF (h1)  [s2]', fontsize=9, color='#16a085')
    ax.text(-1.0, -2.9, 'URLLC UPF (h2)  [s4]', fontsize=9, color='#16a085')

    legend = [
        ('#d35400', 'Core ring switch (s1-s4)'),
        ('#e67e22', 'Edge aggregator (s5-s6)'),
        ('#16a085', 'UPF server'),
        ('#8e44ad', 'eMBB UE (h3,h4)'),
        ('#c0392b', 'URLLC UE (h5,h6)'),
        ('#f39c12', 'mMTC sensor (h7-h9)'),
    ]
    for i, (c, lbl) in enumerate(legend):
        ax.plot([], [], marker='o', ms=12, color=c, ls='', label=lbl)
    ax.legend(loc='lower left', fontsize=9)

    ax.set_title('Astra Mobility 5G Core — SDN Slicing Topology\n'
                 'Ring: 10 Mbps links | gNodeB uplinks: 10 Mbps', fontsize=13)
    ax.axis('off')
    plt.tight_layout()
    plt.savefig(OUT + '/astra_5g_topology.png', dpi=150)
    plt.close()
    print('wrote astra_5g_topology.png')


def draw_performance():
    with open('/tmp/astra_results.json') as f:
        r = json.load(f)

    phases = ['Baseline', 'Rate-Limited', 'Priority QoS']
    urllc_t = [r[p]['urllc_t'] for p in ('baseline', 'rate_limited', 'priority_qos')]
    embb_t = [r[p]['embb_t'] for p in ('baseline', 'rate_limited', 'priority_qos')]
    urllc_l = [r[p]['urllc_l']['avg'] for p in ('baseline', 'rate_limited', 'priority_qos')]
    urllc_j = [r[p]['urllc_l']['jitter'] for p in ('baseline', 'rate_limited', 'priority_qos')]

    colors = ['#bdc3c7', '#f39c12', '#27ae60']

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    ax = axes[0]
    x = range(len(phases))
    w = 0.38
    ax.bar([i - w / 2 for i in x], urllc_t, width=w, label='URLLC', color='#c0392b')
    ax.bar([i + w / 2 for i in x], embb_t, width=w, label='eMBB', color='#8e44ad')
    ax.set_title('Slice Throughput (Mbps)')
    ax.set_xticks(list(x)); ax.set_xticklabels(phases)
    ax.set_ylabel('Mbps'); ax.legend()
    for i, (u, e) in enumerate(zip(urllc_t, embb_t)):
        ax.text(i - w / 2, u + 0.2, f'{u:.1f}', ha='center', fontsize=9)
        ax.text(i + w / 2, e + 0.2, f'{e:.1f}', ha='center', fontsize=9)

    ax = axes[1]
    ax.bar(x, urllc_l, color=colors)
    ax.set_title('URLLC Avg Latency (ms)')
    ax.set_xticks(list(x)); ax.set_xticklabels(phases)
    ax.set_ylabel('ms')
    ax.set_yscale('log')
    for i, v in enumerate(urllc_l):
        ax.text(i, v * 1.15, f'{v:.0f}', ha='center', fontsize=10)
    ax.text(0.5, 0.6, '41x', transform=ax.transAxes, fontsize=20,
            color='#27ae60', fontweight='bold', ha='center')

    ax = axes[2]
    ax.bar(x, urllc_j, color=colors)
    ax.set_title('URLLC Jitter (ms)')
    ax.set_xticks(list(x)); ax.set_xticklabels(phases)
    ax.set_ylabel('ms')
    for i, v in enumerate(urllc_j):
        ax.text(i, v + 5, f'{v:.0f}', ha='center', fontsize=10)

    fig.suptitle('Astra Mobility 5G — QoS Impact on Slice Performance', fontsize=15)
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    plt.savefig(OUT + '/astra_5g_performance.png', dpi=150)
    plt.close()
    print('wrote astra_5g_performance.png')


if __name__ == '__main__':
    draw_topology()
    draw_performance()
