#!/usr/bin/env python3
import sys

# opers
LD = 0
ANDA = 1
ORA = 2
XORA = 3
ADDA = 4
SUBA = 5
ST = 6
Bcc = 7

ROMSIZE = 2 * 64 * 1024
RAMSIZE = 32 * 1024

def decode(N, val):
    """Decoder that returns N values with only one of them true, selected by val"""
    return [val == n for n in range(N)]

def not8(x):
    return ~x & 0xff

def neg8(x):
    return (~x + 1) & 0xff

def add8(x, y):
    return (x + y) & 0xff

def add16(x, y):
    return (x + y) & 0xffff

def add8c(x, y):
    sum = x + y
    result = sum & 0xff
    carry = result != sum # was the sum truncated when putting it into 8-bits?
    return result, carry

class Machine:
    def __init__(self, prog, debug=None):
        if debug is None:
            debug = []
        self.debug = debug

        assert len(prog) == ROMSIZE
        self.prog = prog
        self.ram = [0] * RAMSIZE

        self.pc = 0
        self.ir = 0
        self.d = 0
        self.x = 0
        self.y = 0
        self.acc = 0

        self.inp = 0
        self.outp = 0
        self.ext_outp = 0

        self.last_pc = 0

    def trace(self, tag, s):
        if '*' in self.debug or tag in self.debug:
            print(f"{tag} {s}")

    def fetch_rom(self):
        n = self.pc * 2
        ir = self.prog[n]
        d = self.prog[n+1]
        self.trace('FETCH', f"{self.pc:04x} {ir:02x} {d:02x}")
        return ir, d

    def load_ram(self, addr):
        addr &= 0x7fff # ignore hi bit
        return self.ram[addr]

    def store_ram(self, addr, val):
        addr &= 0x7fff # ignore hi bit
        self.ram[addr] = val

    def step(self):
        """step runs a single cpu instruction."""
        # instruction decode
        ir, d = self.fetch_rom()
        oper = (self.ir>>5) & 7
        mode = (self.ir>>2) & 7
        bus = (self.ir) & 3
        self.trace('EXEC', f"{self.last_pc:04x} ir={self.ir:02x} decode={oper:x}.{mode:x}.{bus:x} d={self.d:02x}")

        if oper != Bcc:
            # decode low/hi/incx
            low, hi, incx = {
                0: lambda: (self.d, 0, 0),       # [D], AC
                1: lambda: (self.x, 0, 0),       # [X], AC
                2: lambda: (self.d, self.y, 0),  # [Y,D], AC
                3: lambda: (self.x, self.y, 0),  # [Y,X], AC
                4: lambda: (self.d, 0, 0),       # [D], X
                5: lambda: (self.d, 0, 0),       # [D], Y
                6: lambda: (self.d, 0, 0),       # [D], OUT
                7: lambda: (self.x, self.y, 1),  # [Y,X++], OUT
            }[mode]()
            addr = (hi << 8) | low

        # select bus value
        b = {
            0: lambda: self.d,
            1: lambda: self.load_ram(addr), # undefined when oper == STORE
            2: lambda: self.acc,
            3: lambda: self.inp,
        }[bus]()

        # write to ram
        if oper == ST:
            self.store_ram(addr, b)

        # alu computation
        alu, co = {
            LD: lambda: (b, False),
            ANDA: lambda: (self.acc & b, False),
            ORA: lambda: (self.acc | b, False),
            XORA: lambda: (self.acc ^ b, False),
            ADDA: lambda: add8c(self.acc, b),
            SUBA: lambda: add8c(self.acc, neg8(b)),
            ST: lambda: (b, False),
            Bcc: lambda: add8c(not8(self.acc), 1), # result is discarded, but carry out is true only if self.acc is zero
        }[oper]()

        # latch alu into target. AC and OUT targets are suppressed for ST.
        if oper != Bcc:
            old_out6 = (self.outp & 0x40) != 0

            if mode == 0 and oper != ST: # [D], AC
                self.acc = alu
            elif mode == 1 and oper != ST: # [X], AC
                self.acc = alu
            elif mode == 2 and oper != ST: # [Y,D], AC
                self.acc = alu
            elif mode == 3 and oper != ST: # [Y,X], AC
                self.acc = alu
            elif mode == 4: # [D], X
                self.x = alu
            elif mode == 5: # [D], Y
                self.y = alu
            elif mode == 6 and oper != ST: # [D], OUT
                self.outp = alu
            elif mode == 7 and oper != ST: # [Y,X++], OUT
                self.outp = alu

            # latch extended output when OUT6 goes from LOW to HI.
            new_out6 = (self.outp & 0x40) != 0
            if not old_out6 and new_out6:
                self.trace('EXT', f"ext_outp {self.acc:02x}")
                self.ext_outp = self.acc

            # increment happens even if write to OUT is suppressed
            if mode == 7: # [Y,X++], OUT
                self.x = add8(self.x, 1)

        # update pc
        self.last_pc = self.pc
        self.pc = add16(self.pc, 1)
        if oper == Bcc:
            # note: cpu computes zero from carry out of "alu" op above (because alu
            # just computed (not(acc) + 1) which only overflows when acc is zero.
            # this uses self.acc, which is the unmodified accumulator result.
            zero = (self.acc == 0)        # true when a-b == 0
            assert zero == co # XXX sanity check, not needed
            neg = (self.acc & 0x80) != 0  # true when a-b < 0
            pos = not neg and not zero    # true when a-b > 0
            take_branch = {
                0: lambda: True,        # long jump (always)
                1: lambda: pos,         # bgt (ac > 0)
                2: lambda: neg,         # blt (ac < 0)
                3: lambda: not zero,    # bne (ac != 0)
                4: lambda: zero,        # beq (ac == 0)
                5: lambda: zero or pos, # bge (ac >= 0)
                6: lambda: zero or neg, # ble (a-b <= 0)
                7: lambda: True,        # bra (always)
            }[mode]()
            #print(f"Bcc mode={mode} take={take_branch}")

            if take_branch and mode == 0: # long jump to page y
                self.pc = (self.y << 8) | b
            if take_branch and mode != 0: # branch within the current page
                self.pc = (self.pc & 0xff00) | b
            if take_branch:
                self.trace('BRANCH', f'took branch to {self.pc:04x}')

        # latch fetched instruction.
        # this probably belongs elsewhere, but we've been using self.ir and self.d above.
        self.ir, self.d = ir, d

        self.trace('STATE', f"pc={self.pc:04x} ir={self.ir:02x} d={self.d:02x} acc={self.acc:02x} x={self.x:02x} y={self.y:02x} out={self.outp:02x}")

def main():
    fn = 'ROMv6.rom'
    rom = open(fn, 'rb').read()

    if 0:
        m = Machine(rom, ['EXEC', 'EXT', 'BRANCH'])
        for _ in range(100):
            m.step()
    if 0:
        m = Machine(rom, ['EXEC', 'EXT'])
        while m.pc < 0x20:
            m.step()
        print(f"{m.pc:04x}")
    if 1:
        m = Machine(rom, ['EXT'])
        while True:
            m.step()

if __name__ == '__main__':
    main()
