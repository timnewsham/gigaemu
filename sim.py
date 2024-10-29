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

class Trace:
    def __init__(self, name, traces):
        self.name = name
        self.traces = traces

    def trace(self, cat, s):
        if self.traces and (cat in self.traces or "*" in self.traces):
            print(f"{self.name} {cat} {s}")

class Rom(Trace):
    """
    A generic 16-bit addressable, 16-bit wide ROM.
    """
    def __init__(self, name, prog, trace=None):
        assert len(prog) == 2 * 64 * 1024
        Trace.__init__(self, name, trace)
        self.data = prog

    def fetch(self, *addr):
        assert len(addr) == 16
        naddr = bit_num(*addr)
        l = self.data[2*naddr]
        h = self.data[2*naddr+1]
        self.trace("FETCH", f"addr={naddr:04x} low={l:02x} hi={h:02x}")
        return num_bits(8, l) + num_bits(8, h)

class Decoder138(Trace):
    """
    74HCT138 is a 3:8 decoder with active-low outputs.
    E1, E2 are active low enables, and E3 is active high.
    """
    def __init__(self, name, trace=None):
        Trace.__init__(self, name, trace)

    def inputs(self, A=(0,0,0), E1=0, E2=0, E3=1):
        self.A = A
        self.E1 = E1
        self.E2 = E2
        self.E3 = E3

        if (E1, E2, E3) == (0, 0, 1):
            self.O = bit_invs(*decode(*self.A))
        else:
            self.O = (1,1,1,1,1,1,1,1)

class Decoder139(Trace):
    """
    74HCT139 is a 2:4 decoder with active-low outputs.
    """
    def __init__(self, name, trace=None):
        Trace.__init__(self, name, trace)

    def inputs(self, A=(0,0), E=0):
        self.A = A
        self.E = E

        if not E:
            self.O = bit_invs(*decode(*self.A))
        else:
            self.O = (1,1,1,1)

class Mux153(Trace):
    """
    74HCT153 is a dual 4:1 mux.
    Ea, Eb are active low enables.
    """
    def __init__(self, name, trace=None):
        Trace.__init__(self, name, trace)

    def inputs(self, Ia=(0,0,0), Ea=0, Ib=(0,0,0), Eb=0, S=(0,0)):
        self.Ia, self.Ea = Ia, Ea
        self.Ib, self.Eb = Ib, Eb
        self.S = S

        if Ea == 0:
            self.Za = mux(*self.Ia)
        else:
            self.Za = 0

        if Eb == 0:
            self.Zb = mux(*self.Ib)
        else:
            self.Zb = 0

class DiodeMatrix(Trace):
    """
    Diode matrix implements wired-nor (or wired-nand for active-low) logic
    with a matrix of diodes.
    The input provides the rows, and the outputs the columns.
    A column is 0 if any of the connected rows are 0, otherwise it is pulled up to 1.
    """
    def __init__(self, name, rows, trace=None):
        assert len(rows) > 0
        self.matrix = rows
        self.nrows = len(rows)
        self.ncols = len(rows[0])
        assert all(len(row) == self.ncols for row in rows)
        Trace.__init__(self, name, trace)

        # we could pre-compute a function for each column for speed.

    def inputs(self, I):
        assert len(I) == self.nrows
        self.I = I

        # this could be a complicated one-liner with loss of clarity
        colvals = []
        for col in range(self.ncols):
            colval = 1 # pull-up
            for row in range(self.rows):
                if I[row] == 0 and self.matrix[row][col] == 1:
                    colval = 0 # grounded through diode
            colvals.append(colval)
        self.O = tuple(colvals)

class Counter161(Trace):
    """
    74HCT161 is a 4-bit counter.
    Reset MR' is not simulated.
    Clock Cp is implicit.
    """
    def __init__(self, name, trace=None):
        Trace.__init__(self, name, trace)
        self.Q = (0,0,0,0)
        self.TC = 0

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

class Reg273(Trace):
    """
    74HCT273 is an 8-bit register.
    Clock Cp is implicit.
    Mr' is not implemented.
    """
    def __init__(self, name, trace=None):
        Trace.__init__(self, name, trace)
        self.Q = (0,0,0,0,0,0,0,0)

    def inputs(self, D=(0,0,0,0,0,0,0,0)):
        assert len(D) == 8
        self.D = D
        self.trace("IN", f"D={D}")

    def clock(self):
        self.trace("LOAD", f"Q={self.Q} -> Q={self.D}")
        self.Q = self.D


# board section

class Board(Trace):
    def __init__(self, name, rom, trace=None):
        Trace.__init__(self, name, trace)

        trace = None #["*"]
        self.rom_u7 = Rom("u7", rom, trace=trace)

        # U1 clock and U2 reset not simulated directly.

        # PC
        trace = None #["*"]
        self.u3_pc03 = Counter161("u3", trace=trace)
        self.u4_pc47 = Counter161("u4", trace=trace)
        self.u5_pc811 = Counter161("u5", trace=trace)
        self.u6_pc1215 = Counter161("u6", trace=trace)

        # IR/D registers
        trace = None #["*"]
        self.u8_ir = Reg273("u8", trace=trace)
        self.u9_d = Reg273("u9", trace=trace)

        # U10 tri-state buffer not simulated directly.

        # instruction decode logic
        trace = None
        self.u11_busaccess = Decoder139("u11", trace=trace)
        self.u12_cond = Mux153("u12", trace=trace)
        self.u13_mode = Decoder138("u13", trace=trace)
        self.u14_instr = Decoder138("u14", trace=trace)

        self.diode_mode = DiodeMatrix("diode_mode", [
            [1, 0, 0, 0],
            [1, 0, 1, 0],
            [1, 0, 0, 1],
            [1, 0, 1, 1],

            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 1, 1, 1],
            ], trace=trace)

        self.diode_isntr = DiodeMatrix("diode_instr", [
            # schematic suggests this diode can be skipped if just using
            # diodes on first column for LD, AND, OR, XOR.
            [1, 0, 0, 0, 0], # IR7

            [0, 0, 0, 1, 1], # LD
            [0, 0, 0, 0, 1], # AND
            [0, 0, 1, 1, 1], # OR
            [0, 0, 1, 1, 0], # XOR
            [0, 0, 0, 1, 1], # ADD
            [0, 1, 1, 0, 0], # SUB
            [0, 0, 0, 0, 0], # ST
            [1, 1, 0, 1, 0], # Bcc
            ], trace=trace)

        # bootstrap values needed before they are updated...
        self.PC = self.u3_pc03.Q + self.u4_pc47.Q + self.u5_pc811.Q + self.u6_pc1215.Q
        assert len(self.PC) == 16

        # XXX
        self.PL = 1
        self.PH = 1
        self.BUS = (0,0,1,1,0,0,1,1)
        self.Y = (1,1,0,0,1,1,0,0)

    def step(self):
        self.clock1_l()
        self.clock1_h()

    def clock1_l(self):
        q = self.rom_u7.fetch(*self.PC)
        self.u8_ir.inputs(D=q[0:8])
        self.u9_d.inputs(D=q[8:16])

        self.u8_ir.clock()
        self.u9_d.clock()

        self.IR = self.u8_ir.Q
        self.D = self.u9_d.Q

        self.u11_busaccess.inputs(A=self.IR[0:2])
        self.DEx, self.OEx, self.AEx, self.IEx = self.u11_busaccess.O

        # tracing...
        n = lambda x : bit_num(*x)
        self.trace("PC", f"pc={n(self.PC):04x} ir={n(self.IR):02x} d={n(self.D):02x}")
        self.trace("BUS", f"DEx={self.DEx} OEx={self.OEx} AEx={self.AEx} IEx={self.IEx}")

    def clock1_h(self):
        # XXX dummy values

        self.u3_pc03.inputs(Pe=self.PL, P=self.BUS[0:4])
        self.u4_pc47.inputs(Pe=self.PL, Cet=self.u3_pc03.TC, P=self.BUS[4:8])
        self.u5_pc811.inputs(Pe=self.PH, Cep=self.PL, Cet=self.u4_pc47.TC, P=self.Y[0:4])
        self.u6_pc1215.inputs(Pe=self.PH, Cep=self.PL, Cet=self.u5_pc811.TC, P=self.Y[4:8])

        self.u3_pc03.clock()
        self.u4_pc47.clock()
        self.u5_pc811.clock()
        self.u6_pc1215.clock()

        self.PC = self.u3_pc03.Q + self.u4_pc47.Q + self.u5_pc811.Q + self.u6_pc1215.Q
        assert len(self.PC) == 16

def test():
    test_prims()

    fn = 'ROMv6.rom'
    rom = open(fn, 'rb').read()

    trace = ['PC']
    m = Board("board", rom, trace=trace)
    for _ in range(10):
        m.step()

if __name__ == '__main__':
    test()
