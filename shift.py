#!/usr/bin/env python3

import argparse
import re
from decimal import *
from gcode_common import *

parser = argparse.ArgumentParser()
parser.add_argument("input", help="input gcode file")
parser.add_argument("x", help="x shift")
parser.add_argument("y", help="y shift")
parser.add_argument("output", help="output gcode file")
args = parser.parse_args()

shift_x = Decimal(args.x)
shift_y = Decimal(args.y)

print(f"Processing: {args.input}")

input = open(args.input)
output = open(args.output, "wt")

for line in input.readlines():
  line = shift_line(line, shift_x, shift_y)
  output.write(line + "\n")

output.close()