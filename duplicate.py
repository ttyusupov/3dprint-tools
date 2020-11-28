#!/usr/bin/env python3

import argparse
import re
from decimal import *
from gcode_common import *

BUILD_MAX_X = 220
BUILD_MAX_Y = 220
BUILD_MAX_Z = 250

def gen_start_item(initial_ext_temp, initial_bed_temp, start_z, idx):
  x2 = BUILD_MAX_X - 20
  y = BUILD_MAX_Y - idx

  if idx == 0:
    home_cmd = "G28 ; home all axes";
  else:
    home_cmd = f"""
G0 F6000 X0 Y{y} Z{start_z}
G28 Z ; home Z axis"""

  output.write(f"""M107 ; turn off fan
M106 S0

{home_cmd}
G0 F6000 Z{start_z} ; move up to have place for filament coming out during pre-heat

M104 S{initial_ext_temp}
M140 S{initial_bed_temp}
M105
M190 S{initial_bed_temp}
M104 S{initial_ext_temp}
M105
M109 S{initial_ext_temp}

G0 F6000 X0 Y{y} Z{start_z}
M82 ; absolute extrusion mode

 M117 Purge extruder
 G92 E0 ; reset extruder
 G1 Z1.0 F3000 ; move z up little to prevent scratching of surface
 G1 X20 Y{y} Z0.3 F5000.0 ; move to start-line position
 G1 X{x2} Y{y} Z0.3 F1500.0 E15 ; draw 1st line
 G1 X{x2} Y{y} Z0.4 F5000.0 ; move to side a little
 G1 X20 Y{y} Z0.4 F1500.0 E30 ; draw 2nd line
 G92 E0 ; reset extruder
 G1 Z{start_z} F3000 ; move z up to prevent scratching of surface and already printed things
G92 E0
G1 F2400 E-2  
""")

def gen_end_item():
  output.write("""
M140 S0
M107
M104 S0 ; turn off extruder
M140 S0 ; turn off bed
G1 X0 Y300 F3000 ; prepare for part removal
M84 ; disable motors
M106 S0 ; turn off fan
M82 ;absolute extrusion mode
M104 S0
""")

def match(re):
  global m, line
  m = re.match(line)
  return m

def min_opt(a, b):
  if a and b:
    return min(a, b)
  elif a:
    return a
  else:
    return b

def max_opt(a, b):
  if a and b:
    return max(a, b)
  elif a:
    return a
  else:
    return b

parser = argparse.ArgumentParser()
parser.add_argument("input", help="input gcode file")
parser.add_argument("x", help="distance from the nozzle to the left side of the extruder, mm")
parser.add_argument("y", help="distance from the nozzle to the front side of the extruder, mm")
parser.add_argument("output", help="output gcode file")
args = parser.parse_args()

ext_reserve_x = Decimal(args.x)
ext_reserve_y = Decimal(args.y)

print(f"Processing: {args.input}")

input = open(args.input)
output = open(args.output, "wt")

initial_bed_temp = None
initial_ext_temp = None
layer_started = False
min_x = None
min_y = None
max_x = None
max_y = None
max_z = None
layer_0_min_x = None
layer_0_max_x = None
layer_0_min_y = None
layer_0_max_y = None
model_lines = []

for line in input.readlines():
  line = line.rstrip()
  if match(SET_BED_TEMP_RE):
    temp = Decimal(m.group(1))
    if not initial_bed_temp:
      initial_bed_temp = temp
    if layer_started and temp == 0:
      break
  elif match(SET_EXT_TEMP_RE):
    temp = Decimal(m.group(1))
    if not initial_ext_temp:
      initial_ext_temp = temp
    if layer_started and temp == 0:
      break
  elif match(LAYER_COUNT_RE):
    layer_started = True
  elif match(LAYER_START_RE):
    layer_started = True
    layer_idx = int(m.group(1))
  elif G01_RE.match(line):
    if layer_started:
      move = gparseMove(line)
      if move.get("Z"):
        z = Decimal(move["Z"])
      if move.get("E"):
        if max_z:
          max_z = max(max_z, z)
        else:
          max_z = z
      if move.get("X"):
        x = Decimal(move["X"])
        if layer_idx > 0:
          min_x = min_opt(min_x, x)
          max_x = max_opt(max_x, x)
        else:
          layer_0_min_x = min_opt(layer_0_min_x, x)
          layer_0_max_x = max_opt(layer_0_max_x, x)
      if move.get("Y"):
        y = Decimal(move["Y"])
        if layer_idx > 0:
          min_y = min_opt(min_y, x)
          max_y = max_opt(max_y, x)
        else:
          layer_0_min_y = min_opt(layer_0_min_y, y)
          layer_0_max_y = max_opt(layer_0_max_y, y)
  if layer_started:
    model_lines.append(line)

print("Build bounds: x:", min_x, max_x, "y:", min_y, max_y, "z:", max_z)
print("Layer 0 bounds: x:", layer_0_min_x, layer_0_max_x, "y:", layer_0_min_y, layer_0_max_y)
size_x = max_x - min_x
size_y = max_y - min_y
print("Build size: x:", size_x, "y:", size_y)
layer_0_size_x = layer_0_max_x - layer_0_min_x
layer_0_size_y = layer_0_max_y - layer_0_min_y
print("Layer 0 size: x:", layer_0_size_x, "y:", layer_0_size_y)

dist_x = max(layer_0_max_x - min_x + ext_reserve_x, layer_0_size_x + 1)
dist_y = max(layer_0_max_y - min_y + ext_reserve_y, layer_0_size_y + 1)

print("Dist x:", dist_x, "y:", dist_y)

start_z = min(BUILD_MAX_Z, max_z + 30)

for idx in range(0, 9):
  print("Generating copy", idx + 1)
  shift_x = (idx % 3 - 1) * dist_x
  shift_y = (idx // 3 - 1) * dist_y
  gen_start_item(initial_ext_temp, initial_bed_temp, start_z, idx)
  output.write(
    f"G1 X{layer_0_min_x + shift_x} Y{layer_0_min_y + shift_y} Z{start_z} F3000 "
    f"; pre-move at top z to avoid scratching already printed things\n")
  for line in model_lines:
    output.write(shift_line(line, shift_x, shift_y) + "\n")
  gen_end_item()

output.close()