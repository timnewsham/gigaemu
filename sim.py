#!/usr/bin/env python3
"""
This is a bit-level simulation of the gigatron board based on the 2018-05-10 schematic.

The implementation is done at a medium level of abstraction:
Each chip is simulated at a logical level but not at a gate level or timing level.
Simulation is done in a linear fashion, and gating/latching of values is
done at specific points in the linear simulation with no attention
to simulating the asynchronous behavior of the signals.

Signals are treated as bits that can be zero or one for low
and high (not necessarily their logical values of True and False,
which would be True for 1 in active-high logic, and True for 0
in active-low logic).

Helper functions with names like "and" and "or" are named for their
active-high logic function.

TODO: not simulating reset conditions right now.
"""

# primitives section

def bit(bool):
    return 1 if bool else 0

def bit_inv(b):
    return bit(b == 0)

def bit_invs(*bs):
    return tuple([bit_inv(b) for b in bs])

def bit_and(*bs):
    return bit(all(b == 1 for b in bs))

def bit_or(*bs):
    return bit(any(b == 1 for b in bs))

def mux(n, *bs):
    return bs[n]

def bit_num(*bs): # lowest bit first
    return sum((b << shift) for shift, b in enumerate(bs))

def num_bits(sz, n):
    return tuple([(n >> shift) & 1 for shift in range(sz)])

def decode(*bs):
    sz = 1 << len(bs)
    n = bit_num(*bs)
    return tuple([bit(m == n) for m in range(sz)])

def test_prims():
    assert bit(False) == 0
    assert bit(True) == 1
    assert bit_inv(0) == 1
    assert bit_inv(1) == 0
    assert bit_invs(0,1,1) == (1,0,0)
    assert bit_and(1,1,1,1)
    assert not bit_and(1,1,0,1)
    assert bit_or(0,0,1,0)
    assert not bit_or(0, 0, 0, 0)
    assert mux(2, 1,0,0,0) == 0
    assert mux(2, 1,0,1,0) == 1
    assert bit_num(1,0,0) == 1
    assert num_bits(3, 3) == (1, 1, 0)
    assert num_bits(3, 6) == (0, 1, 1)
    assert bit_num(0,1,1) == 6
    assert decode(1,0) == (0,1,0,0)
    assert decode(1,1) == (0,0,0,1)

# chips section

class Rom:
    """
    A generic 16-bit addressable, 16-bit wide ROM.
    """
    def __init__(self, name, prog, debug=None):
        assert len(prog) == 2 * 64 * 1024
        self.name = name
        self.data = prog
        self.debug = debug

    def trace(self, cat, s):
        trace(self.name, self.debug, cat, s)

    def fetch(self, *addr):
        assert len(addr) == 16
        naddr = bit_num(*addr)
        l = self.data[2*naddr]
        h = self.data[2*naddr+1]
        self.trace("FETCH", f"addr={naddr:04x} low={l:02x} hi={h:02x}")
        return num_bits(8, l) + num_bits(8, h)

def trace(name, dbg, cat, s):
    if dbg and (cat in dbg or "*" in dbg):
        print(f"{name} {cat} {s}")

class Counter161:
    """
    74HCT161 is a 4-bit counter.
    Reset MR' is not simulated.
    Clock Cp is implicit.

    TC simulation is not a look-ahead as in the actual chip.
    It reflects the carry out of Q after Q has been latched.
    This means updating counters needs to be done in careful order.
    """
    def __init__(self, name, debug=None):
        self.name = name
        self.debug = debug
        self.Q = (0,0,0,0)
        self.TC = 0

    def trace(self, cat, s):
        trace(self.name, self.debug, cat, s)

    def inputs(self, Cep=1, Cet=1, Pe=0, P=(0,0,0,0)):
        assert len(P) == 4
        self.Cep = Cep
        self.Cet = Cet
        self.Pe = Pe
        self.P = P

        self.TC = bit(Cet and self.Q == (1,1,1,1))
        self.trace("IN", f"Cep={Cep} Cet={Cet} Pe={Pe} P={P} -> TC={self.TC}")

    def clock(self):
        if not self.Pe: # load
            self.trace("LOAD", f"P={P}")
            self.q = self.P
        elif self.Cep and self.Cet: # count
            oldq = self.Q
            (b0,b1,b2,b3, c) = num_bits(5, bit_num(*self.Q) + 1)
            self.Q = b0,b1,b2,b3
            self.trace("COUNT", f"Q={oldq} -> Q={self.Q}")
        else:
            self.trace("HOLD", f"Q={self.Q}")

# board section

class Board:
    def __init__(self, name, rom, debug=None):
        self.name = name
        self.debug = debug

        debug = None #["*"]
        self.rom_u7 = Rom("u7", rom, debug=debug)

        # PC
        debug = None #["*"]
        self.pc03_u3 = Counter161("u3", debug=debug)
        self.pc47_u4 = Counter161("u4", debug=debug)
        self.pc811_u5 = Counter161("u5", debug=debug)
        self.pc1215_u6 = Counter161("u6", debug=debug)

    def trace(self, cat, s):
        trace(self.name, self.debug, cat, s)

    def step(self):
        self.clock1_l()
        self.clock1_h()

    def clock1_h(self):
        # XXX dummy values
        PL = 1
        PH = 1
        BUS = (0,0,1,1,0,0,1,1)
        Y = (1,1,0,0,1,1,0,0)

        self.pc03_u3.inputs(Pe=PL, P=BUS[0:4])
        self.pc47_u4.inputs(Pe=PL, Cet=self.pc03_u3.TC, P=BUS[4:8])
        self.pc811_u5.inputs(Pe=PH, Cep=PL, Cet=self.pc47_u4.TC, P=Y[0:4])
        self.pc1215_u6.inputs(Pe=PH, Cep=PL, Cet=self.pc811_u5.TC, P=Y[4:8])

        self.pc03_u3.clock()
        self.pc47_u4.clock()
        self.pc811_u5.clock()
        self.pc1215_u6.clock()

    def clock1_l(self):
        self.PC = self.pc03_u3.Q + self.pc47_u4.Q + self.pc811_u5.Q + self.pc1215_u6.Q
        assert len(self.PC) == 16
        q = self.rom_u7.fetch(*self.PC)
        ir = q[0:8]
        d = q[8:16]

        # TODO: latch this into IR/D

        npc = bit_num(*self.PC)
        nir = bit_num(*ir)
        nd = bit_num(*d)
        self.trace("PC", f"pc={npc:04x} ir={nir:02x} d={nd:02x}")

def test():
    test_prims()

    fn = 'ROMv6.rom'
    rom = open(fn, 'rb').read()

    m = Board("board", rom, debug=['*'])
    for _ in range(10):
        m.step()

if __name__ == '__main__':
    test()
