# Gigaemu

This directory has some files that let me explore the gigatron computer design.

* [emu.py](emu.py) emulates the computer.
* [sim.py](sim.py) simulates the schematic's logic, but not the timing or exact pin-by-pin values. It has a fairly good mechanism for stepping, watching and tracing execution, but only at the API level so far. It could use a debugging shell.
  * [sim\_test.py](sim_test.py) runs tests on the simulator looking to see if it behaves properly.

## In Progress

* The simulator has been tested quite a bit with `sim_test.py`.
* The emulator seems to work well, but hasnt been rigorously tested.
* The emulator and simulator should be tested against each other.
* A lot more could be done to support I/O or live debugging and probing.
