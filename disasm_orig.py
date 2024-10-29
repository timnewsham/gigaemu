#!/usr/bin/env python3
import sys

opernames = [
    "LOAD",
    "AND",
    "OR",
    "XOR",

    "ADD",
    "SUB",
    "STORE",
    "JUMP",
]

modenames = [
    "[D],AC",
    "[X],AC",
    "[Y,D],AC",
    "[Y,X],AC",

    "[D],X",
    "[D],Y",
    "[D],OUT",
    "[Y,X++],OUT",
]

storemodenames = [
    "[D]",
    "[X]",
    "[Y,D]",
    "[Y,X]",

    "[D],X",
    "[D],Y",
    "[D]",
    "[Y,X++]",
]

jumpmodenames = [
    "far",
    "gt",
    "lt",
    "ne",

    "eg",
    "ge",
    "le",
    "alw",
]

busnames = [ "D", "RAM", "AC", "IN" ]
storebusnames = [ "D", "CTRL", "AC", "IN" ]
jumpbusnames = [ "D", "[D]", "AC", "IN" ]

def disasm(fn):
    f = open(fn, 'rb')
    addr = 0
    while True:
        bs = f.read(2)
        if bs == b'':
            break
        insn,op = bs
        oper = (insn>>5) & 7
        mode = (insn>>2) & 7
        bus = (insn) & 3

        opername = opernames[oper]
        modename = modenames[mode]
        busname = busnames[bus]
        if opername == 'STORE':
            modename = storemodenames[mode]
            busname = storebusnames[bus]
        elif opername == 'JUMP':
            modename = jumpmodenames[mode]
            busname = jumpbusnames[bus]

        if busname == 'CTRL':
            opername = 'CTRL'
        
        print(f"{fn} {addr:04x} {insn:02x}.{op:02x} : {opername:5s} {modename:9s} {busname:4s} ${op:02x}")
        addr += 1

def main():
    for fn in sys.argv[1:]:
        disasm(fn)

main()
