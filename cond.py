#!/usr/bin/env python3

def decoder(n, *opts):
    return opts[n]

# There are four combinations of N (AC7) and Z (CO) flags.
conds = [
    "a > 0",  # ~Z, ~N, its not zero, its not negative, its positive.
    "a < 0",  # ~Z, N, its not zero, it is negative, its negative.
    "a == 0", # Z, ~N, its zero and its not negative, its zero.
    "NEVER",  # Z, N, its both zero and negative, which can never happen.
]

# the opcode "mode" bits select a condition code when performing a Bcc instruction.
# These are selected with a 4:1 decoder using the N and Z flags in the circuit,
# using the three mode bits IR2, IR3, and IR4.
# The IR2 bit is selected when Z=0, N=0. ie. when a>0.
# The IR3 bit is selected when Z=0, N=1, ie when a<0.
# The IR4 bit is selected when Z=1, N=0, ie. when a=0.
# When Z=1 and N=1, which can't happen, the decoder selects a zero output.
#
# This means we can read each of the mode bits as three cases:
# - either a>0 (IR2)
# - a<0 (IR3)
# - or a=0 (IR4).
#
# Then the table can mode bits can be read as some combination of those three conditions
# that will allow a true condition to be output. (the fourth posibility of a=0 and a<0 can be ignored).
#
# Note: extra logic handles the "JMP" case and forces it to be true always, as well as generate
# extra signals for special handling of long jumps.
ccs = [
    #           # | IR4 a=0 | IR3 a<0 | IR2 a>0 ||
    "JMP",      # |   0     |    0    |    0    || always outputs false         : never
    "GT",       # |   0     |    0    |    1    || true when a>0                : a>0
    "LT",       # |   0     |    1    |    0    || true when a<0                : a<0
    "NE",       # |   0     |    1    |    1    || true when a<0 or a>0         : a!=0
    "EQ",       # |   1     |    0    |    0    || true when a=0                : a=0
    "GE",       # |   1     |    0    |    1    || true when a=0 or a>0         : a>=0
    "LE",       # |   1     |    1    |    0    || true when a=0 or a<0         : a<=0
    "ALWAYS",   # |   1     |    1    |    1    || true when a=0 or a<0 or a>0  : always
]


# lets try it out
d = {}
for cc in ccs:
    d[cc] = []
# we'll try out each condition code (all 7 mode posibilities)
for ccnum, cc in enumerate(ccs):
    print(cc, end=': ')
    # and each condition (all four cases, although the fourth case can never be true)
    for condnum, cond in enumerate(conds):
        # extract the 3 bits of the cc number
        ir2 = ccnum & 1
        ir3 = (ccnum>>1)&1
        ir4 = (ccnum>>2)&1

        # and use a decoder to pick one of them, just like the circuit does
        take_branch = decoder(condnum, ir2, ir3, ir4, 0)

        # and keep a list of which conditions resulted in taking the branch for each condition code
        if take_branch:
            print(cond, end=', ')
    print()


