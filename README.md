# Gigaemu

This directory has some files that let me explore the gigatron computer design.

* [emu.py](emu.py) emulates the computer.
* [sim.py](sim.py) simulates the schematic's logic, but not the timing or exact pin-by-pin values. It has a fairly good mechanism for stepping, watching and tracing execution, but only at the API level so far. It could use a debugging shell.
  * [sim\_test.py](sim_test.py) runs tests on the simulator looking to see if it behaves properly.
* [sim\_emu\_cmp.py](sim_emu_cmp.py) runs emu and sim in lock-step to compare their execution state.

## TODO
* A lot more could be done to support I/O or live debugging and probing.
