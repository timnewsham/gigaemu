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

ramnames = [
    "[D]",
    "[X]",
    "[Y,D]",
    "[Y,X]",

    "[D]",
    "[D]",
    "[D]",
    "[Y,X]",
]

targnames = [
    'AC',
    'AC',
    'AC',
    'AC',

    'X',
    'Y',
    'OUT',
    'OUT',
]

jumpnames = [
    "JUMP Y,",
    "BGT",
    "BLT",
    "BNE",

    "BEQ",
    "BGE",
    "BLE",
    "BRA",
]

busnames = [ "D", "RAM", "AC", "IN" ]
storebusnames = [ "D", "CTRL", "AC", "IN" ]

def disasm1(bs):
    insn,op = bs
    oper = (insn>>5) & 7
    mode = (insn>>2) & 7
    bus = (insn) & 3

    opername = opernames[oper]

    incrname = ""
    if mode == 7:
        incrname = " (x++)"

    busname = busnames[bus]

    srcname = busnames[bus].replace('D', f"${op:02x}")
    srcname = srcname.replace('RAM', ramnames[mode].replace('D', f"${op:02x}"))
    targname = targnames[mode]

    if opername == 'JUMP':
        jumpname = jumpnames[mode]
        line = f"{jumpname} ${op:02x}"

    elif opername == 'STORE':
        #targname = targname.replace(",AC", "-")
        #targname = targname.replace(",OUT", "-")

        # "RAM" is meaningless except with extension board, where it means control.
        #if busname == 'RAM':
        #    busname = 'CTRL'
        #    opername = 'CTRL'

        srcname = busnames[bus].replace('D', f"${op:02x}")
        if srcname == 'RAM':
            srcname = '-'
            opername = 'CTRL'
        targname = ramnames[mode].replace('D', f"${op:02x}")

        # AC and OUT are suppressed
        targname2 = targnames[mode].replace('AC', '').replace('OUT', '')
        if targname2:
            targname = targname + "," + targname2

        line = f"{opername} {srcname},{targname}{incrname}"

    else:
        srcname = busnames[bus].replace('D', f"${op:02x}")
        srcname = srcname.replace('RAM', ramnames[mode].replace('D', f"${op:02x}"))
        targname = targnames[mode]

        line = f"{opername} {srcname},{targname}{incrname}"
    return oper, mode, bus, op, line

def disasm(fn):
    f = open(fn, 'rb')
    addr = 0
    while True:
        bs = f.read(2)
        if bs == b'':
            break

        oper, mode, bus, op, line = disasm1(bs)
        print(f"{fn} {addr:04x} {oper:x}.{mode:x}.{bus:x}.{op:02x} : {line}")
        addr += 1

def main():
    for fn in sys.argv[1:]:
        disasm(fn)

if __name__ == '__main__':
    main()
