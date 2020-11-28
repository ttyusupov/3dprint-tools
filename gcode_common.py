#!/usr/bin/env python3

import re
from decimal import *

LAYER_START_RE = re.compile("\s*;LAYER:(\d+)")
LAYER_COUNT_RE = re.compile("\s*;LAYER_COUNT:(\d+)")
G01_RE = re.compile("\s*G[01]\s+(.*)")
SET_EXT_TEMP_RE = re.compile("\s*M104\s+S(\d+)")
SET_BED_TEMP_RE = re.compile("\s*M140\s+S(\d+)")

def gparseMove(line):
  result = {}
  command_with_comment = line.strip().split(";", maxsplit=1)
  command = command_with_comment[0].strip()
  if len(command_with_comment) > 1:
    result[';'] = command_with_comment[1]
  for g in command.split(" "):
    result[g[0]] = g[1:]
  return result

def genMove(move):
  line = f"G{move['G']}"
  for k, v in move.items():
    if k != 'G' and k != ';':
      line += f" {k}{v}"
  if move.get(';'):
    line += f" ;{move[';']}"
  return line

def shift_line(line, shift_x, shift_y):
  line = line.rstrip()

  if G01_RE.match(line):
    move = gparseMove(line)
    if move.get('X'):
      move['X'] = Decimal(move['X']) + shift_x
    if move.get('Y'):
      move['Y'] = Decimal(move['Y']) + shift_y
    line = genMove(move)
  return line
