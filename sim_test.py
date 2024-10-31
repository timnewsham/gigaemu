#!/usr/bin/env python3

import sim
from sim import num_bits, bit_num

LD, AND, OR, XOR, ADD, SUB, ST, Bcc = tuple(range(8))
D_AC, X_AC, YD_AC, YX_AC, D_X, D_Y, D_OUT, YXpp_OUT = tuple(range(8))
DATA, RAM, AC, IN = tuple(range(4))
JMP, GT, LT, NE, EQ, GE, LE, BRA = tuple(range(8))

n = lambda bs: bit_num(*bs)

def mkbits(sz, x):
    if isinstance(x, int):
        x = num_bits(sz, x)
    return x

def instr(instr, mode, bus, imm):
    instr = mkbits(3, instr)
    mode = mkbits(3, mode)
    bus = mkbits(2, bus)
    assert isinstance(imm, int)

    b1 = n(bus + mode + instr)
    b2 = imm
    return [b1, b2]

nop = instr(LD, D_AC, AC, 0)

def run(*instrs, trace=None, pokes=()):
    """
    load up instrs into a machine and run it for
    as many steps as there are instructions.
    """
    # load up instrs into rom, prefix with a nop.
    rinstrs = []
    rinstrs += nop
    for instr in instrs:
        rinstrs += instr
    #print(rinstrs)

    rom = [0] * 2 * 64 * 1024
    ninstrs = len(rinstrs)>>1
    rom[:len(rinstrs)] = list(rinstrs)

    m = sim.Gigatron("board", rom, trace=trace)
    for addr,val in pokes:
        m.u36_ram.store(num_bits(15, addr), num_bits(8, val))

    m.step() # first instruction runs twice, do the first one now.
    for _ in range(ninstrs):
        m.step()
    return m, ninstrs

def test_nop(trace=None):
    m,cnt = run(nop, trace=trace)
    assert n(m.exec_pc) == cnt
    assert n(m.PC) == cnt + 1
    assert n(m.AC) == 0
    assert n(m.X) == 0
    assert n(m.Y) == 0
    assert n(m.OUT) == 0

def test_ld_acc_val(val, trace=None):
    m, cnt = run(instr(LD, D_AC, DATA, val), trace=trace)
    assert n(m.AC) == val
def test_ld_x_val(val, trace=None):
    m, cnt = run(instr(LD, D_X, DATA, val), trace=trace)
    assert n(m.X) == val
def test_ld_y_val(val, trace=None):
    m, cnt = run(instr(LD, D_Y, DATA, val), trace=trace)
    assert n(m.Y) == val
def test_ld_out_val(val, trace=None):
    m, cnt = run(instr(LD, D_OUT, DATA, val), trace=trace)
    assert n(m.OUT) == val

def test_ld_reg(trace=None):
    for val in range(256):
        test_ld_acc_val(val, trace=trace)
        test_ld_x_val(val, trace=trace)
        test_ld_y_val(val, trace=trace)
        test_ld_out_val(val, trace=trace)

def test_st_zp_addrval(addr, val, trace=None):
    m,cnt = run(
        instr(LD, D_AC, DATA, val),
        instr(ST, D_AC, AC, addr),
        instr(LD, D_AC, DATA, 0),
        instr(LD, D_AC, RAM, addr),
        trace = trace)
    assert n(m.AC) == val

def test_st_zp(trace=None):
    addr = 0x11
    for val in range(256):
        test_st_zp_addrval(addr, val, trace=trace)

def test_aluop_ab(op, a, b, expect, trace=None):
    m,cnt = run(
        instr(LD, D_AC, DATA, a),
        instr(op, D_AC, DATA, b),
        trace=trace)
    assert n(m.AC) == expect

def test_aluop(trace=None):
    test_aluop_ab(AND, 0x11, 0x0f, 0x01, trace=trace)
    test_aluop_ab(AND, 0xf0, 0xff, 0xf0, trace=trace)
    test_aluop_ab(OR, 0x11, 0x0f, 0x1f, trace=trace)
    test_aluop_ab(OR, 0xf0, 0x0c, 0xfc, trace=trace)
    test_aluop_ab(XOR, 0x11, 0x0f, 0x1e, trace=trace)
    test_aluop_ab(XOR, 0xf0, 0x0c, 0xfc, trace=trace)
    test_aluop_ab(ADD, 0xff, 0x01, 0x00, trace=trace)
    test_aluop_ab(ADD, 0x01, 0xff, 0x00, trace=trace)
    test_aluop_ab(ADD, 20, 33, 53, trace=trace)
    test_aluop_ab(ADD, 33, 256-20, 13, trace=trace)
    test_aluop_ab(SUB, 20, 33, 256-13, trace=trace)
    test_aluop_ab(SUB, 20, 3, 17, trace=trace)
    test_aluop_ab(SUB, 0, 1, 0xff, trace=trace)

def test_longjump(trace=None):
    targhi = 0x11
    targlo = 0x8f
    ldval = 0xec
    m,cnt = run(
        instr(LD, D_Y, DATA, targhi),
        instr(Bcc, JMP, DATA, targlo),
        instr(LD, D_AC, DATA, ldval), # delay slot
        trace=trace)
    assert n(m.AC) == ldval
    assert n(m.exec_pc) == cnt
    assert n(m.PC) == (targhi << 8) | targlo

def test_branch_cond(val, cond, taken, trace=None):
    targ = 0x8f
    ldval = 0x99
    m,cnt = run(
        instr(LD, D_AC, DATA, val),
        instr(Bcc, cond, DATA, targ),
        instr(LD, D_AC, DATA, ldval), # delay slot
        trace=trace)
    assert n(m.AC) == ldval
    assert n(m.exec_pc) == cnt
    if taken:
        assert n(m.PC) == targ
    else:
        assert n(m.PC) == cnt+1

def test_branch(trace=None):
    test_branch_cond(0x0f, GT, True, trace=trace)
    test_branch_cond(0x00, GT, False, trace=trace)
    test_branch_cond(0xf0, GT, False, trace=trace)

    test_branch_cond(0x0f, LT, False, trace=trace)
    test_branch_cond(0x00, LT, False, trace=trace)
    test_branch_cond(0xf0, LT, True, trace=trace)

    test_branch_cond(0x0f, NE, True, trace=trace)
    test_branch_cond(0x00, NE, False, trace=trace)
    test_branch_cond(0xf0, NE, True, trace=trace)

    test_branch_cond(0x0f, EQ, False, trace=trace)
    test_branch_cond(0x00, EQ, True, trace=trace)
    test_branch_cond(0xf0, EQ, False, trace=trace)

    test_branch_cond(0x0f, GE, True, trace=trace)
    test_branch_cond(0x00, GE, True, trace=trace)
    test_branch_cond(0xf0, GE, False, trace=trace)

    test_branch_cond(0x0f, LE, False, trace=trace)
    test_branch_cond(0x00, LE, True, trace=trace)
    test_branch_cond(0xf0, LE, True, trace=trace)

    test_branch_cond(0x0f, BRA, True, trace=trace)
    test_branch_cond(0x00, BRA, True, trace=trace)
    test_branch_cond(0xf0, BRA, True, trace=trace)

def test_st_mode(mode, base_addr=0x11, acval=0x22, xval=0x33, yval=0x44, expected_addr=None, expected_xval=None, expected_yval=None, trace=None):
    if expected_xval is None:
        expected_xval = xval
    if expected_yval is None:
        expected_yval = yval

    m,cnt = run(
        instr(LD, D_AC, DATA, acval),
        instr(LD, D_X, DATA, xval),
        instr(LD, D_Y, DATA, yval),
        instr(ST, mode, AC, base_addr),
        trace=trace)

    ram_val = m.u36_ram.fetch(num_bits(15, expected_addr))
    #print(f"{expected_addr:04x}: {n(ram_val):02x}, X={n(m.X):02x} Y={n(m.Y):02x}")
    assert n(ram_val) == acval
    assert n(m.X) == expected_xval
    assert n(m.Y) == expected_yval

def test_st_modes(trace=None):
    lohi = lambda l,h : (h << 8) | l

    test_st_mode(D_AC, base_addr=0x99, expected_addr=0x99, trace=trace)
    test_st_mode(X_AC, xval=0x99, expected_addr=0x99, trace=trace)
    test_st_mode(YD_AC, base_addr=0x88, yval=0x99, expected_addr=lohi(0x88, 0x99), trace=trace)
    test_st_mode(YX_AC, xval=0x88, yval=0x99, expected_addr=lohi(0x88, 0x99), trace=trace)

    # These are weirdos.. they store acval into both ram and the target (X or Y) register.
    test_st_mode(D_X, acval=0xaa, base_addr=0x88, xval=0x99, expected_addr=0x88, expected_xval=0xaa, trace=trace)
    test_st_mode(D_Y, acval=0xaa, base_addr=0x88, yval=0x99, expected_addr=0x88, expected_yval=0xaa, trace=trace)

    test_st_mode(D_OUT, base_addr=0x99, expected_addr=0x99, trace=trace)

    # This one increments X.
    test_st_mode(YXpp_OUT, xval=0x88, yval=0x99, expected_addr=lohi(0x88, 0x99), expected_xval=0x89, trace=trace)

def test_ld_mode(mode, targ_addr=0x11, targ_val=0x22, acval=0x33, xval=0x44, yval=0x55, immval=0x66, expected_xval=None, expected_yval=None, expected_acval=None, trace=None):
    if expected_xval is None:
        expected_xval = xval
    if expected_yval is None:
        expected_yval = yval
    if expected_acval is None:
        expected_acval = acval

    # machine starts with zero'd ram except targ_addr with targ_val.
    m,cnt = run(
        instr(LD, D_AC, DATA, acval),
        instr(LD, D_X, DATA, xval),
        instr(LD, D_Y, DATA, yval),
        instr(LD, mode, RAM, immval),
        trace=trace,
        pokes=[(targ_addr, targ_val)])

    #print(f"AC={n(m.AC):02x} X={n(m.X):02x} Y={n(m.Y):02x}")
    assert n(m.AC) == expected_acval
    assert n(m.X) == expected_xval
    assert n(m.Y) == expected_yval

def test_ld_modes(trace=None):
    lohi = lambda l,h : (h << 8) | l

    test_ld_mode(D_AC, targ_addr=0x99, targ_val=0x88, immval=0x99, acval=0xaa, expected_acval=0x88, trace=trace)
    test_ld_mode(X_AC, targ_addr=0x99, targ_val=0x88, xval=0x99, acval=0xaa, expected_acval=0x88, trace=trace)
    test_ld_mode(YD_AC, targ_addr=lohi(0x99,0xaa), targ_val=0x88, immval=0x99, yval=0xaa, acval=0xbb, expected_acval=0x88, trace=trace)
    test_ld_mode(YX_AC, targ_addr=lohi(0x99,0xaa), targ_val=0x88, xval=0x99, yval=0xaa, acval=0xbb, expected_acval=0x88, trace=trace)
    test_ld_mode(D_X, targ_addr=0x99, targ_val=0x88, immval=0x99, xval=0xaa, expected_xval=0x88, trace=trace)
    test_ld_mode(D_Y, targ_addr=0x99, targ_val=0x88, immval=0x99, yval=0xaa, expected_yval=0x88, trace=trace)
    test_ld_mode(D_OUT, targ_addr=0x99, targ_val=0x88, immval=0x99, trace=trace) # TODO: expected_out
    test_ld_mode(YXpp_OUT, targ_addr=lohi(0x99,0xaa), targ_val=0x88, xval=0x99, yval=0xaa, expected_xval=0x9a, trace=trace) # TODO: expected_out

def test():
    trace=None
    test_nop(trace=trace)
    test_ld_reg(trace=trace)
    test_st_zp(trace=trace)
    test_aluop(trace=trace)
    test_branch(trace=trace)
    test_longjump(trace=trace)
    test_st_modes(trace=trace)
    test_ld_modes(trace=trace)

    # TODO: test ld/st/bcc bus modes
    # TODO: Bcc, addressing modes

def fixme():
    trace = [
        "REG",
        "DECODE",
        "ADDR",
        "RAM",
        #"u3:*", "u4:*", "u5:*", "u6:*", # PC reg
    ]
    #test_ld_modes(trace=trace)
    pass

if __name__ == '__main__':
    test()
    fixme()
