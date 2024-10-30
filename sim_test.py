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

def run(*instrs, trace=None):
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

def test_branch_cond(val, cond, taken, trace=None):
    targ = 0x8f
    ldval = 0x99
    m,cnt = run(
        instr(LD, D_AC, DATA, val),
        instr(Bcc, cond, DATA, targ),
        instr(LD, D_AC, DATA, ldval),
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

def test():
    trace=None
    test_nop(trace=trace)
    test_ld_reg(trace=trace)
    test_st_zp(trace=trace)
    test_aluop(trace=trace)
    test_branch(trace=trace)

    # TODO: load addressing modes
    # TODO: store addressing modes
    # TODO: Bcc, addressing modes
    # TODO: long jump, addressing modes

def fixme():
    trace = ["REG", "DECODE",
        "u3:*", "u4:*", "u5:*", "u6:*", # PC reg
    ]

    pass

if __name__ == '__main__':
    test()
    fixme()
