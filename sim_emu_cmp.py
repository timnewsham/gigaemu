#!/usr/bin/env python3

import sim
import emu

n = lambda bs: sim.bit_num(*bs)

def model_check(rom, simtrace=None, emutrace=None):
    machsim = sim.Gigatron("board", rom, trace=simtrace)
    machemu = emu.Machine(rom, debug=emutrace)

    #machsim.step() # step the first dummy instruction

    step = 0
    while True:
        fail = None
        if n(machsim.fetched_pc) != machemu.last_pc:
            fail = f"SIM PC={n(machsim.fetched_pc):04x} EMU PC={machemu.last_pc:04x}"
        #elif n(machsim.IR) != machemu.ir:
        #    fail = f"SIM IR={n(machsim.IR):02x} EMU IR={machemu.ir:02x}"
        #elif n(machsim.D) != machemu.d:
        #    fail = f"SIM D={n(machsim.D):02x} EMU D={machemu.d:02x}"
        elif n(machsim.AC) != machemu.acc:
            fail = f"SIM AC={n(machsim.AC):02x} EMU AC:{machemu.acc:02x}"
        elif n(machsim.X) != machemu.x:
            fail = f"SIM X={n(machsim.X):02x} EMU X:{machemu.x:02x}"
        elif n(machsim.Y) != machemu.y:
            fail = f"SIM Y={n(machsim.Y):02x} EMU Y:{machemu.y:02x}"
        elif n(machsim.OUT) != machemu.outp:
            fail = f"SIM OUT={n(machsim.OUT):02x} EMU OUT:{machemu.outp:02x}"
        # ext out?

        if fail is not None:
            print(f"step {step}: PC={machemu.last_pc:04x}: {fail}")
            assert False

        machsim.step()
        machemu.step()
        if simtrace or emutrace:
            print()
        step += 1

def main():
    fn = 'ROMv6.rom'
    simtrace = None
    emutrace = None
    #simtrace = ['DECODE', 'REG', 'BRANCH', 'COND']
    #emutrace = ['EXEC', 'FETCH', 'STATE']
    rom = open(fn, 'rb').read()
    model_check(rom, simtrace=simtrace, emutrace=emutrace)

if __name__ == '__main__':
    main()
