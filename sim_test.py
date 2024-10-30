#!/usr/bin/env python3

import sim
from sim import num_bits, bit_num

LD, AND, OR, XOR, ADD, SUB, ST, Bcc = tuple(range(8))
D_AC, X_AC, YD_AC, YX_AC, D_X, D_Y, D_OUT, YXpp_OUT = tuple(range(8))
JMP, GT, LT, NE, EQ, GE, LE, BRA = tuple(range(8))
DATA, RAM, AC, IN = tuple(range(4))

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

    b1 = n(instr + mode + bus)
    b2 = imm
    return [b1, b2]

nop = instr(LD, D_AC, DATA, 0)

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

    rom = [0] * 2 * 64 * 1024
    ninstrs = len(rinstrs)
    rom[:len(rinstrs)] = list(rinstrs)

    m = sim.Gigatron("board", rom, trace=trace)
    m.step() # first instruction runs twice, do the first one now.
    for _ in range(ninstrs):
        m.step()
    return m, ninstrs

def test_empty():
    m,cnt = run(nop)
    assert n(m.exec_pc) == cnt
    assert n(m.PC) == cnt + 1
    assert n(m.AC) == 0
    assert n(m.X) == 0
    assert n(m.Y) == 0
    assert n(m.OUT) == 0
    

def test():
    test_empty()

test()
