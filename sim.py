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

import disasm

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

def get_field(v, fn):
    """
    get_field(foo, "bar[3].baz") returns foo.bar[3].baz.
    """
    make_hex = False
    if fn.startswith('hex:'):
        make_hex = True
        fn = fn[4:]

    while fn:
        if fn.startswith('.'):
            fn = fn[1:]

        if fn.startswith('['): # index into v
            idx, fn = fn[1:].split(']', 1)
            if isinstance(v, tuple) or isinstance(v, list):
                if ':' in idx:
                    a,b = idx.split(':')
                    v = v[int(a) : int(b)]
                else:
                    v = v[int(idx)]
            else:
                v = v[idx]

        else: # access field in fn
            # split on first dot or bracket
            dot = fn.find('.')
            bracket = fn.find('[')
            if bracket != -1 and (bracket < dot or dot == -1):
                # split at bracket, keeping the bracket
                cur, fn = fn[:bracket], fn[bracket:]
            elif dot != -1 and (dot < brakcet or bracket == -1):
                # split at dot, discarding the dot
                cur, fn = fn[:dot], fn[dot:]
            else:
                cur, fn = fn, None

            v = v.__getattribute__(cur)

    if make_hex:
        v = hex(bit_num(*v))
    return v

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

    class Obj: pass
    o = Obj()
    o.x = [Obj() for n in range(3)]
    o.x[1].a = 'a'
    o.x[2] = {"hi": Obj()}
    o.x[2]["hi"].y = 23
    assert get_field(o, "x[1].a") == 'a'
    assert get_field(o, 'x[2][hi].y') == 23

class Trace:
    def __init__(self, name, traces):
        # Trace names can specify a module name with a "name:" prefix.
        # Filter out all trace names that arent for this module, and
        # strip the module name prefix.
        if traces is None:
            traces = []
        prefix = name + ":"
        mytraces = []
        for tracename in traces:
            if ':' in tracename:
                if tracename.startswith(prefix):
                    newname = tracename[len(prefix):]
                    mytraces.append(newname)
            else:
                mytraces.append(tracename)

        self.name = name
        self.traces = mytraces
        self.watch_every = True
        self.watches = {}
        self.prev = {}

    def trace(self, cat, s):
        if cat in self.traces or "*" in self.traces:
            print(f"{self.name}:{cat} {s}")

    def _gets(self):
        return dict((k, get_field(self, v)) for k,v in self.watches.items())

    def watcher(self):
        cur = self._gets()
        vs = []
        for nm in sorted(self.prev):
            if self.watch_every:
                vs.append(f"{nm}:{cur[nm]}")
            elif cur[nm] != self.prev[nm]:
                vs.append(f"{nm}:{self.prev[nm]}->{cur[nm]}")
        if vs:
            print(f"{self.name} WATCH {' '.join(vs)}")
        self.prev = cur

    def watch(self, every, **watches):
        self.watch_every = every
        self.watches = watches
        self.prev = self._gets()

# chips section

class DiodeMatrix(Trace):
    """
    Diode matrix implements wired-and (or wired-or for active-low) logic
    with a matrix of diodes.
    The input provides the rows, and the outputs the columns.
    The matrix[row][col] is 1 if there's diode tieing the column to the input row.
    A column value is 0 if any of the connected rows are 0, otherwise it is pulled up to 1.
    """
    def __init__(self, name, matrix, trace=None):
        assert len(matrix) > 0
        self.matrix = matrix
        self.nrows = len(matrix)
        self.ncols = len(matrix[0])
        assert all(len(row) == self.ncols for row in self.matrix)
        Trace.__init__(self, name, trace)

        # we could pre-compute a function for each column for speed.

    def inputs(self, I):
        assert len(I) == self.nrows
        self.I = I

        # this could be a complicated one-liner with loss of clarity
        colvals = []
        for col in range(self.ncols):
            colval = 1 # pull-up
            for row in range(self.nrows):
                if I[row] == 0 and self.matrix[row][col] == 1:
                    colval = 0 # grounded through diode
            colvals.append(colval)
        assert len(colvals) == self.ncols
        self.O = tuple(colvals)

class Rom(Trace):
    """
    A generic 16-bit addressable, 16-bit wide ROM.
    """
    def __init__(self, name, prog, trace=None):
        assert len(prog) == 2 * 64 * 1024
        Trace.__init__(self, name, trace)
        self.data = prog

    def fetch(self, A):
        assert len(A) == 16
        addr = bit_num(*A)
        l = self.data[2*addr]
        h = self.data[2*addr+1]
        self.trace("FETCH", f"A={addr:04x} D={l:02x}:{h:02x}")
        self.A = A
        self.D = num_bits(8, l) + num_bits(8, h)
        return self.D

class Ram(Trace):
    """
    A generic 15-bit addressable, 8-bit wide RAM.
    WE is implictly handled by the clock method.
    """
    def __init__(self, name, trace=None):
        Trace.__init__(self, name, trace)
        self.data = [0] * (32 * 1024)

    def fetch(self, A):
        assert len(A) == 15
        addr = bit_num(*A)
        d = self.data[addr]
        self.trace("FETCH", f"A={addr:04x} -> D={d:02x}")
        self.A = A
        self.D = num_bits(8, d)
        return self.D

    def store(self, A, D):
        assert len(A) == 15
        assert len(D) == 8
        addr = bit_num(*A)
        d = bit_num(*D)
        self.trace("STORE", f"A={addr:04x} D={d:02x}")
        self.data[addr] = d

class Decoder138(Trace):
    """
    74HCT138 is a 3:8 decoder with active-low outputs.
    E1, E2 are active low enables, and E3 is active high.
    """
    def __init__(self, name, trace=None):
        Trace.__init__(self, name, trace)

    def inputs(self, A=(0,0,0), E1=0, E2=0, E3=1):
        assert len(A) == 3
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
    74HCT139 is a dual 2:4 decoder with active-low outputs.
    """
    def __init__(self, name, trace=None):
        Trace.__init__(self, name, trace)

    def inputs(self, Ea=0, Aa=(0,0), Eb=0, Ab=(0,0)):
        self.Aa, self.Ea = Aa, Ea
        self.Ab, self.Eb = Ab, Eb

        if not Ea:
            self.Oa = bit_invs(*decode(*self.Aa))
        else:
            self.Oa = (1,1,1,1)
        if not Eb:
            self.Ob = bit_invs(*decode(*self.Ab))
        else:
            self.Ob = (1,1,1,1)

class Mux153(Trace):
    """
    74HCT153 is a dual 4:1 mux.
    Ea, Eb are active low enables.
    """
    def __init__(self, name, trace=None):
        Trace.__init__(self, name, trace)

    def inputs(self, Ia=(0,0,0,0), Ea=0, Ib=(0,0,0,0), Eb=0, S=(0,0)):
        assert len(Ia) == 4
        assert len(Ib) == 4
        assert len(S) == 2
        self.Ia, self.Ea = Ia, Ea
        self.Ib, self.Eb = Ib, Eb
        self.S = S

        n = bit_num(*self.S)
        if Ea == 0:
            self.Za = mux(n, *self.Ia)
        else:
            self.Za = 0

        if Eb == 0:
            self.Zb = mux(n, *self.Ib)
        else:
            self.Zb = 0

class Mux157(Trace):
    """
    74HCT157 is a quad 2:1 mux.
    E is an active low enable.
    """
    def __init__(self, name, trace=None):
        Trace.__init__(self, name, trace)

    def inputs(self, Ia=(0,0,0,0), Ib=(0,0,0,0), E=0, S=0):
        assert len(Ia) == 4
        assert len(Ib) == 4
        self.Ia = Ia
        self.Ib = Ib
        self.E = E
        self.S = S

        if self.E:
            self.Z = mux(self.S, self.Ia, self.Ib)
        else:
            self.Z = (0,0,0,0)

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

    def inputs(self, Cep=1, Cet=0, Pe=1, P=(0,0,0,0)):
        assert len(P) == 4
        self.Cep = Cep
        self.Cet = Cet
        self.Pe = Pe
        self.P = P

        if self.Cet and self.Q == (1,1,1,1):
            self.TC = 1
        else:
            self.TC = 0
        self.trace("IN", f"Cep={Cep} Cet={Cet} Pe={Pe} P={P} -> TC={self.TC}")

    def clock(self):
        if not self.Pe: # load
            self.trace("LOAD", f"P={self.P}")
            self.Q = self.P
        elif self.Cep and self.Cet: # count
            oldq = self.Q
            (b0,b1,b2,b3, c) = num_bits(5, bit_num(*self.Q) + 1)
            self.Q = b0,b1,b2,b3
            self.trace("COUNT", f"Q={oldq} -> Q={self.Q}")
        else:
            self.trace("HOLD", f"Q={self.Q}")

        # XXX duplicate this here after update?
        if self.Cet and self.Q == (1,1,1,1):
            self.TC = 1
        else:
            self.TC = 0

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

class Adder283(Trace):
    """
    74HCT283 is a 4-bit adder.
    """
    def __init__(self, name, trace=None):
        Trace.__init__(self, name, trace)

    def inputs(self, A=(0,0,0,0), B=(0,0,0,0), CO=0):
        assert len(A) == 4
        assert len(B) == 4
        a = bit_num(*A)
        b = bit_num(*B)
        sum = num_bits(5, a+b+CO)
        self.S = sum[0:4]
        self.C4 = sum[4]
        self.trace("ADD", f"A={A} B={B} CO={CO} -> S={self.S} C4={self.C4}")

class Reg377(Trace):
    """
    74HCT377 is an 8-bit register with enable.
    """
    def __init__(self, name, trace=None):
        Trace.__init__(self, name, trace)
        self.Q = (0,0,0,0,0,0,0,0)

    def inputs(self, D=(0,0,0,0,0,0,0,0), EO=0):
        assert len(D) == 8
        self.D = D
        self.EO = EO
        self.trace("IN", f"D={D} EO={EO}")

    def clock(self):
        if self.EO == 0:
            self.trace("LOAD", f"Q={self.Q} -> Q={self.D}")
            self.Q = self.D
        else:
            self.trace("HOLD", f"Q={self.Q}")

class Shift595(Trace):
    """
    74HCT595 is an 8-bit shift register with output enable, clear,
    serial clock, read clock and clear.
    Clear and enables not implemented.
    Assumes both clocks are tied together as in the gigatron.
    """
    def __init__(self, name, trace=None):
        Trace.__init__(self, name, trace)
        self.SR = (0,0,0,0,0,0,0,0)
        self.Q = (0,0,0,0,0,0,0,0)

    def inputs(self, SER=0):
        self.SER = SER
        self.trace("IN", f"SER={SER}")

    def clock(self):
        oldq, oldsr = self.Q, self.SR
        # latches old SR before shifting in SER in.
        self.Q = self.SR
        self.SR = (self.SER,) + self.SR[0:7]
        self.trace("SHIFT", f"Q={oldq} -> Q={self.Q}, SR={oldsr} -> SR={self.SR}")

# board section

class Gigatron(Trace):
    """
    The gigatron board.

    Notes:
    - After initialization the first instruction runs twice due to pipelining
      (instruction 0 is in its own delay slot).
    """
    def __init__(self, name, rom, trace=None):
        Trace.__init__(self, name, trace)

        self.serial_input = 0

        # U1 clock not explicit.
        # U2 reset not simulated.
        self.u3_pc = Counter161("u3", trace=trace)
        self.u4_pc = Counter161("u4", trace=trace)
        self.u5_pc = Counter161("u5", trace=trace)
        self.u6_pc = Counter161("u6", trace=trace)
        self.u7_rom = Rom("u7", rom, trace=trace)
        self.u8_ir = Reg273("u8", trace=trace)
        self.u9_d = Reg273("u9", trace=trace)
        # U10 tri-state buffer not simulated directly.
        self.u11_busjmp = Decoder139("u11", trace=trace) # two decoders, one for busaccess, one for jmp
        self.u12_cond = Mux153("u12", trace=trace)
        self.u13_mode = Decoder138("u13", trace=trace)
        self.u14_instr = Decoder138("u14", trace=trace)
        # U15 octal inverter not represented. See comments later.
        # U16 quad or not represented. See comments later.

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

        self.diode_instr = DiodeMatrix("diode_instr", [
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

        self.u17_alulogic = Mux153("u17", trace=trace)
        self.u18_alulogic = Mux153("u18", trace=trace)
        self.u19_alulogic = Mux153("u19", trace=trace)
        self.u20_alulogic = Mux153("u20", trace=trace)
        self.u21_alulogic = Mux153("u21", trace=trace)
        self.u22_alulogic = Mux153("u22", trace=trace)
        self.u23_alulogic = Mux153("u23", trace=trace)
        self.u24_alulogic = Mux153("u24", trace=trace)
        self.u25_aluadd = Adder283("u25", trace=trace)
        self.u26_aluadd = Adder283("u26", trace=trace)
        self.u27_regac = Reg377("u27", trace=trace)
        # U28 tri-state buffer not simulated directly.
        self.u29_regx = Counter161("u29", trace=trace)
        self.u30_regx = Counter161("u30", trace=trace)
        self.u31_regy = Reg377("u31", trace=trace)
        self.u32_addr = Mux157("u32", trace=trace)
        self.u33_addr = Mux157("u33", trace=trace)
        self.u34_addr = Mux157("u34", trace=trace)
        self.u35_addr = Mux157("u35", trace=trace)
        self.u36_ram = Ram("u36", trace=trace)
        self.u37_regout = Reg377("u37", trace=trace)
        self.u38_extout = Reg273("u38", trace=trace)
        self.u39_inp = Shift595("u39", trace=trace)

        # give values to all signals to inert values
        # clock_l:
        self.PC = (0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0)
        self.exec_pc = self.PC
        self.IR = (0,0,0,0,0,0,0,0)
        self.D = (0,0,0,0,0,0,0,0)
        # updated in instr_decode:
        self.DEx = 1
        self.BFx = 1
        self.Wx = 1
        self.W = 0
        self.XLx = 1
        self.YLx = 1
        self.IX = 0
        self.EL = 0
        self.EH = 0
        self.LDx = 1
        self.OLx = 1
        self.ALx = 0
        self.AR = (0,0,0,0)
        self.PHx = 1
        self.PLx = 1
        self.A = (0,0,0,0,0,0,0,0)
        self.ADDR_A = (0,0,0,0,0,0,0,0)
        self.ADDR_B = (0,0,0,0,0,0,0,0)
        self.ALU = (0,0,0,0,0,0,0,0)
        self.CO = 0
        self.WEx = 1
        # updated in clock2_l
        self.AC = (0,0,0,0,0,0,0,0)
        self.X = (0,0,0,0,0,0,0,0)
        self.Y = (0,0,0,0,0,0,0,0)
        self.OUT = (0,0,0,0,0,0,0,0)
        self.RGB = (0,0,0)
        self.HSYNCx = 0
        self.VSYNCx = 0
        self.SER_PULSE = 0
        self.SER_LATCH = 0
        self.BUS = (0,0,0,0,0,0,0,0)
        # updated in clock_out6_l
        self.LED = (0,0,0,0)
        self.AUDIO = (0,0,0,0)
        self.IN = (0,0,0,0,0,0,0,0)

        # load up rom output values
        self.u7_rom.fetch(self.PC)

    def step(self):
        n = lambda x : bit_num(*x)
        self.trace("REG", f"PC={n(self.exec_pc):04x} AC={n(self.AC):02x} X={n(self.X):02x} Y={n(self.Y):02x} IN={n(self.IN):02x} OUT={n(self.OUT):02x}")

        self.clock1_l()
        self.instr_decode()
        self.clock2_l()
        self.clock1_l_post()
        self.watcher()

    def clock1_l(self):
        self.exec_pc = self.PC # we're still executing the last fetched instruction

        self.u3_pc.inputs(Pe=self.PLx, Cet=1, P=self.BUS[0:4])
        self.u4_pc.inputs(Pe=self.PLx, Cet=self.u3_pc.TC, P=self.BUS[4:8])
        self.u5_pc.inputs(Pe=self.PHx, Cep=self.PLx, Cet=self.u4_pc.TC, P=self.Y[0:4])
        self.u6_pc.inputs(Pe=self.PHx, Cep=self.PLx, Cet=self.u5_pc.TC, P=self.Y[4:8])
        self.u8_ir.inputs(D=self.u7_rom.D[0:8])
        self.u9_d.inputs(D=self.u7_rom.D[8:16])

        self.u3_pc.clock()
        self.u4_pc.clock()
        self.u5_pc.clock()
        self.u6_pc.clock()
        self.u7_rom.fetch(self.PC)
        self.u8_ir.clock()
        self.u9_d.clock()

        self.PC = self.u3_pc.Q + self.u4_pc.Q + self.u5_pc.Q + self.u6_pc.Q
        assert len(self.PC) == 16
        self.IR = self.u8_ir.Q
        self.D = self.u9_d.Q

        n = lambda x : bit_num(*x)
        b = lambda x : bit_num(*x).to_bytes(1)
        if self.PLx == 0 or self.PHx == 0:
            self.trace("BRANCH", f"target {n(self.PC):04x} PLx={self.PLx} PHx={self.PHx} BUS={n(self.BUS):02x}")

        _, _, _, _, line = disasm.disasm1(b(self.IR) + b(self.D))
        self.trace("DECODE", f"PC={n(self.exec_pc):04x} IR={n(self.IR):02x} D={n(self.D):02x}: {line}")

    def instr_decode(self):
        # logic based on IR/D
        self.u11_busjmp.inputs(Aa=self.IR[0:2], Ea=0, Ab=self.IR[2:4], Eb=self.IR[4])
        self.DEx, self.OEx, self.AEx, self.IEx = self.u11_busjmp.Oa
        self.BFx = self.u11_busjmp.Ob[0]

        self.u14_instr.inputs(A=self.IR[5:8])
        self.Wx = self.u14_instr.O[6]
        self.W = bit_inv(self.Wx) # U15 1 of 8.

        ia = self.IR[2:5] + (0,)
        sel = (self.AC[7], self.CO)
        self.u12_cond.inputs(Ia=ia, Ib=(1,1,1,1), S=sel, Ea=self.u14_instr.O[7]) # after u14 updated
        self.u13_mode.inputs(A=self.IR[2:5], E3=self.u14_instr.O[7]) # after u14 updated
        self.XLx = self.u13_mode.O[4]
        self.YLx = self.u13_mode.O[5]
        self.IX = bit_inv(self.u13_mode.O[7]) # U15 1 of 8

        self.diode_mode.inputs(self.u13_mode.O) # after u13 updated
        self.EL = self.diode_mode.O[2]
        self.EH = self.diode_mode.O[3]
        self.LDx = bit_or(self.diode_mode.O[0], self.W) # after self.W updated, U16 1 of 4.
        self.OLx = bit_or(self.diode_mode.O[1], self.W) # after self.W updated, U16 1 of 4.

        inp = (self.IR[7],) + self.u14_instr.O
        self.diode_instr.inputs(inp) # after u14 updated

        self.ALx = bit_inv(self.diode_instr.O[0])    # after diode_instr updated, U15 1 of 8.
        self.AR = bit_invs(*self.diode_instr.O[1:5]) # after diode_instr updated, U15 5 of 8.

        phx = bit_or(self.u14_instr.O[7], self.BFx) # after u11/u14 updated, U16 1 of 4.
        self.PHx = phx
        cond = self.u12_cond.Za
        self.PLx = bit_and(bit_inv(cond), phx) # inv from U15 1 of 8, AND implemented with diodes and pull-up.

        # Note: I "rewired" these to keep the input lines in-order.
        # The schematic has some lines out of order on these muxes for routing reasons.
        self.u34_addr.inputs(Ia=self.X[0:4], Ib=self.D[0:4], S=self.EL)
        self.u35_addr.inputs(Ia=self.X[4:8], Ib=self.D[4:8], S=self.EL)
        self.u32_addr.inputs(Ia=self.Y[0:4], Ib=(1,1,1,1), S=0, E=self.EH)
        self.u33_addr.inputs(Ia=self.Y[4:8], Ib=(1,1,1,1), S=0, E=self.EH)
        self.A = self.u34_addr.Z + self.u35_addr.Z + self.u32_addr.Z + self.u33_addr.Z

        # ram, D might need to appear on bus before ALU logic and clock2_l
        self.update_bus(True)

        self.u21_alulogic.inputs(Ia=self.AR, Ib=(0,1,0,1), S=(self.AC[0], self.BUS[0]), Ea=0, Eb=self.ALx)
        self.u22_alulogic.inputs(Ia=self.AR, Ib=(0,1,0,1), S=(self.AC[1], self.BUS[1]), Ea=0, Eb=self.ALx)
        self.u23_alulogic.inputs(Ia=self.AR, Ib=(0,1,0,1), S=(self.AC[2], self.BUS[2]), Ea=0, Eb=self.ALx)
        self.u24_alulogic.inputs(Ia=self.AR, Ib=(0,1,0,1), S=(self.AC[3], self.BUS[3]), Ea=0, Eb=self.ALx)
        # I "rewired" the Ia and Ib lines on the next four to keep them in AR bit order.
        # The schematic juggles (AR0,AR2,AR1,AR3), swaps S bits, and swaps Ia and Ib, swaps Ea and Eb.
        self.u17_alulogic.inputs(Ia=self.AR, Ib=(0,1,0,1), S=(self.AC[4], self.BUS[4]), Ea=0, Eb=self.ALx)
        self.u18_alulogic.inputs(Ia=self.AR, Ib=(0,1,0,1), S=(self.AC[5], self.BUS[5]), Ea=0, Eb=self.ALx)
        self.u19_alulogic.inputs(Ia=self.AR, Ib=(0,1,0,1), S=(self.AC[6], self.BUS[6]), Ea=0, Eb=self.ALx)
        self.u20_alulogic.inputs(Ia=self.AR, Ib=(0,1,0,1), S=(self.AC[7], self.BUS[7]), Ea=0, Eb=self.ALx)

        self.ADDR_A = (
            self.u21_alulogic.Za, self.u22_alulogic.Za, self.u23_alulogic.Za, self.u24_alulogic.Za,
            self.u17_alulogic.Za, self.u18_alulogic.Za, self.u19_alulogic.Za, self.u20_alulogic.Za,
        )
        self.ADDR_B = (
            self.u21_alulogic.Zb, self.u22_alulogic.Zb, self.u23_alulogic.Zb, self.u24_alulogic.Zb,
            self.u17_alulogic.Zb, self.u18_alulogic.Zb, self.u19_alulogic.Zb, self.u20_alulogic.Zb,
        )
        self.u26_aluadd.inputs(A=self.ADDR_A[0:4], B=self.ADDR_B[0:4], CO=self.AR[0])
        self.u25_aluadd.inputs(A=self.ADDR_A[4:8], B=self.ADDR_B[4:8], CO=self.u26_aluadd.C4)
        self.ALU = self.u26_aluadd.S + self.u25_aluadd.S
        self.CO = self.u25_aluadd.C4
        self.trace("ALU", f"AR={self.AR} AC={self.AC} BUS={self.BUS} A={self.ADDR_A} B={self.ADDR_B} C={self.AR[0]} S={self.ALU} CO={self.CO}")

        # WEx comes from bit_or(CLK1, Wx), but we don't have explicit clock signals.
        # it will latch RAM when Wx is true (0) and CLK1 goes low.
        # This omits the U16 1 of 4 in the simulation.
        self.WEx = self.Wx

        # tracing...
        n = lambda x : bit_num(*x)
        self.trace("PC", f"pc={n(self.PC):04x} ir={n(self.IR):02x} d={n(self.D):02x}")

    def clock2_l(self):
        self.u27_regac.inputs(D=self.ALU, EO=self.LDx)
        self.u29_regx.inputs(P=self.ALU[0:4], Pe=self.XLx, Cep=self.IX, Cet=1)
        self.u30_regx.inputs(P=self.ALU[4:8], Pe=self.XLx, Cep=self.IX, Cet=self.u29_regx.TC)
        self.u31_regy.inputs(D=self.ALU, EO=self.YLx)
        self.u37_regout.inputs(D=self.ALU, EO=self.OLx)

        self.u27_regac.clock()
        self.u29_regx.clock()
        self.u30_regx.clock()
        self.u31_regy.clock()
        self.u37_regout.clock()

        old_out6 = self.OUT[6]

        self.AC = self.u27_regac.Q
        self.X = self.u29_regx.Q + self.u30_regx.Q
        self.Y = self.u31_regy.Q
        self.OUT = self.u37_regout.Q
        self.RGB = bit_num(*self.OUT[0:2]), bit_num(*self.OUT[2:4]), bit_num(*self.OUT[4:6])
        self.HSYNCx = self.OUT[6]
        self.VSYNCx = self.OUT[7]
        self.SER_PULSE = self.OUT[6]
        self.SER_LATCH = self.OUT[7]

        out6 = self.OUT[6]
        if old_out6 == 1 and out6 == 0:
            self.clock_out6_l()

    def clock1_l_post(self):
        # Note: this really happens in clock1_l of the next instruction,
        # but I want to account for it in the current execution step when simulating.

        # AC, IN might need to appear on the bus
        self.update_bus(False)

        # WEx is (Wx AND clock1) in schematic, but just Wx for us.
        # we only evalute it in clock1_l, triggering ram store when low.
        if self.WEx == 0:
            self.u36_ram.store(self.A[0:15], self.BUS)
            n = lambda x : bit_num(*x)
            self.trace("RAM", f"STORE {n(self.BUS):02x} to {n(self.A):04x}")


    def update_bus(self, show_ram):
        # Simulate the tri-state bus. This isn't clocked but change after registers change.
        assert self.DEx + self.OEx + self.AEx + self.IEx == 3 # three will be false (one) and one will be true (zero).
        if self.DEx == 0:
            self.BUS = self.D
        elif self.OEx == 0:
            self.BUS = self.u36_ram.fetch(self.A[0:15])
            if show_ram:
                n = lambda x : bit_num(*x)
                self.trace("RAM", f"FETCH {n(self.BUS):02x} from {n(self.A):04x}")
        elif self.AEx == 0:
            self.BUS = self.AC
        elif self.IEx == 0:
            self.BUS = self.IN
        else:
            self.BUS = None
            assert False, "bus multiplexer error"
        self.trace("BUS", f"DEx={self.DEx} OEx={self.OEx} AEx={self.AEx} IEx={self.IEx} -> BUS={self.BUS}")

    def clock_out6_l(self):
        self.u38_extout.inputs(D=self.AC)
        self.u39_inp.inputs(SER=self.serial_input)

        self.u38_extout.clock()
        self.u39_inp.clock()

        self.LED = self.u38_extout.Q[0:4]
        self.AUDIO = self.u38_extout.Q[4:8]
        self.IN = self.u39_inp.Q

def test():
    test_prims()

    fn = 'ROMv6.rom'
    rom = open(fn, 'rb').read()

    trace = [
        "REG",
        "DECODE",
        "BRANCH",
        "u3:*", "u4:*", "u5:*", "u6:*", # PC reg
        #"BUS",
        #"RAM"
        #"ALU",

        #'board:PC',
        #'u3:COUNT',
        #'HOLD', 'COUNT', 'LOAD',
    ]
    m = Gigatron("board", rom, trace=trace)
    #m.watch(True, PCLO="hex:PC[0:8]", WE="WEx")
    #m.watch(False, PCLO="hex:PC[0:8]", WE="WEx")
    m.watch(True, BUS="hex:BUS", PL="PLx", PH="PHx")
    for _ in range(20000):
        m.step()

if __name__ == '__main__':
    test()
