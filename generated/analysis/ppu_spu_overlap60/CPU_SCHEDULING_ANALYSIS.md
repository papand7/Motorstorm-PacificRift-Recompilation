# CPU_SCHEDULING_ANALYSIS
- VERIFIED (Test A): 4.0-4.2 game cores + 1.5-1.6 other cores busy of 6 cores/12 threads; GPU 48%. Wws lanes average 1.54 of 5 busy (Kksr77). No average saturation.
- VERIFIED (trace): usleep(200) hand-offs take ~550 us on the host timer, a wake-latency effect on the job hand-off path.
- Not measured: context switches, SMT sibling sharing, ready-queue delay, cache/memory bandwidth.
- Needed (needs authorization for a race): ETW CPU-sample/context-switch trace of one race.
- HYPOTHESIS: wake latency, not saturation, costs time. No affinity or priority change proposed.
