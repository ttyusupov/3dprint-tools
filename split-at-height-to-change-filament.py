#!/usr/bin/env python3

import argparse
import re
from decimal import *
from gcode_common import *

BUILD_MAX_X = 220
BUILD_MAX_Y = 220
BUILD_MAX_Z = 250

SET_FAN_LEVEL_RE = re.compile("M106\s+S(\d+)")

def switch_output():
  global output
  global output_num
  if output:
    output.close()
  output_num += 1
  output = open(f"{input_filepath_ext[0]}-{output_num}.{input_filepath_ext[1]}", "wt")

def gen_prepare_to_change():
  global z

  output.write(f""";TYPE:CUSTOM PREPARE TO CHANGE FILAMENT
;current z: {z}
M83 ; Set extruder to relative mode
G1 E-10.000000 F2400 ; Retract
M106 S0 ; Turn off fan
M107
M104 S0 ; Turn off extruder heat
M140 S0 ; Turn off bed heat
G1 X10.000000 Y10.000000 F3000 ; Move head away
G1 Z{max(z+1, 50)} F3000 ; Move head up to at least z=50, but higher than it was
G0 E-100 F2400 ; Turn out filament
M400 ; Wait for buffer to clear
M84 ; Disable motors
M300 ; Beep
""")

def gen_prepare_to_continue_print():
  global initial_ext_temp, bed_temp, e, x, y, z

  if not initial_ext_temp:
    raise Exception("initial_ext_temp not set")
  output.write(f""";TYPE:CUSTOM PREPARE TO CONTINUE PRINT
M107 ; Turn off fan
M117 Heating extruder and bed...
M140 S{bed_temp}
M104 S{initial_ext_temp}
M105
M190 S{bed_temp}
M109 S{initial_ext_temp}

M82 ;absolute extrusion mode

G0 F6000 X0 Y{BUILD_MAX_Y} Z{max(z+1, 50)} ; move closer to start-line
 M117 Purge extruder
 G92 E0 ; reset extruder
 G1 X20 Y{BUILD_MAX_Y} Z0.3 F5000.0 ; move to start-line position
 G1 X200.0 Y{BUILD_MAX_Y} Z0.3 F1500.0 E15 ; draw 1st line
 G1 X200.0 Y{BUILD_MAX_Y} Z0.4 F5000.0 ; move to side a little
 G1 X20 Y{BUILD_MAX_Y} Z0.4 F1500.0 E30 ; draw 2nd line
 G92 E0 ; reset extruder
 G1 Z1.0 F3000 ; move z up little to prevent scratching of surface
G92 E0
G1 F2400 E-2

G0 Z{z+1} F6000 ; Move to Z position higher than next layer
G0 X{x} Y{y} F6000 ; Move to next layer position
G0 Z{z} F6000 ; Move to next layer Z position

G92 E{e} ; Set the extrude value to the previous value
;CUSTOM PREPARE TO CONTINUE PRINT DONE

""")

def gen_split():
  gen_prepare_to_change()
  switch_output()
  gen_prepare_to_continue_print()

def gen_restore_ext_temp():
  global ext_temp

  output.write(f"""; Set extruder temp back
M104 S{ext_temp}
""")

def gen_fan_set(level):
  output.write(f"M106 S{level}\n")

def match(re):
  global m, line
  m = re.match(line)
  return m

parser = argparse.ArgumentParser()
parser.add_argument("input", help="input gcode file")
parser.add_argument("z", help="z coordinate to split from")
args = parser.parse_args()

split_z = Decimal(args.z)
input_filepath_ext = args.input.split(".", maxsplit=1)

print(f"Processing: {args.input}")

input = open(args.input)
output = None
output_num = 0
switch_output()

initial_ext_temp = None
layer_comment = None
layer_idx = 0
layer_z = None
copy_to_output = True
buf = []
copy_to_buf = False
split_found = False
layer_after_split = None
fan_switch = {}

for line in input.readlines():
  line = line.rstrip()
  if LAYER_START_RE.match(line):
    layer_idx += 1
    layer_comment = line
    layer_z = None
    if split_found:
      layer_after_split += 1
    if layer_after_split == 2:
      gen_restore_ext_temp()
    if fan_switch.get(layer_after_split):
      gen_fan_set(fan_switch.get(layer_after_split))
  elif SET_EXT_TEMP_RE.match(line):
    ext_temp = SET_EXT_TEMP_RE.match(line).group(1)
    if not initial_ext_temp:
      initial_ext_temp = ext_temp
  elif SET_BED_TEMP_RE.match(line):
    bed_temp = SET_BED_TEMP_RE.match(line).group(1)
  elif match(SET_FAN_LEVEL_RE):
    fan_switch[layer_idx] = m.group(1)
  elif G01_RE.match(line):
    move = gparseMove(line)
    if move.get('X'):
      x = Decimal(move.get('X'))
    if move.get('Y'):
      y = Decimal(move.get('Y'))
    if move.get('Z'):
      z = Decimal(move['Z'])
      if not split_found and z >= split_z:
        split_found = True
        print("Splitting at layer:", layer_comment)
        gen_split()
        layer_after_split = 0
    if layer_comment and move.get('E'):
      e = move['E']
      if not layer_z:
        layer_z = z

  if copy_to_output:
    output.write(line + "\n")
  if copy_to_buf:
    buf.append(line)

output.close()
