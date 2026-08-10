# Topology Fixes Design

## Overview
This design addresses two errors that occur when running `astra_5g_topo.py`:
1. `sch_htb: quantum of class 50001 is big. Consider r2q change.`
2. `ovs-ofctl: unknown command 'get-config'` during the DPID check.

## Approach
1. **HTB Quantum Warning**: The warning is triggered by `tc` because of the `bw=100` constraints on edge/host links. Since the core ring links are already bottlenecks at `10 Mbps`, we will remove `bw=100` from all host-to-switch and node-to-switch edge attachments (keeping `delay='1ms'`). This eliminates the mathematical errors with HTB while preserving the correct lab simulation topology.
2. **DPID Check Error**: The code calls `sw.dpctl('get-config')`, which is not supported in newer `ovs-ofctl` versions with OpenFlow 1.3. We will replace this with the native Mininet Python API attribute `sw.dpid`.

## Required Changes
- Modify `astra_5g_topo.py`
  - Remove `bw=100` arguments from `self.addLink()` calls for `h1` through `h9`.
  - Replace `sw.dpctl('get-config')` with `sw.dpid` in the DPID check loop.
