#!/usr/bin/env python3

# Very simple debug of the coordinate extraction

davis_warning = """NAVAREA IV 1292/25(15).
DAVIS STRAIT.
22 OCEAN BOTTOM MOORINGS DEPLOYED
ONE METER ABOVE OCEAN FLOOR UNTIL
FURTHER NOTICE, IN:
A. 61-32.92N 059-23.18W 2230 METERS.
B. 61-20.01N 058-47.40W 2545 METERS.
V. 60-13.29N 058-33.87W 2635 METERS.
ANY INQUIRIES CAN BE DIRECTED TO GRAEME
CAIRNS AT NFSI (GRAEME.CAIRNS@DAL.CA) OR
ALEXANDRE PLOURDE AT NRCAN
(ALEXANDRE.PLOURDE@NRCAN-RNCAN.GC.CA).
191207Z NOV 25"""

lines = davis_warning.split('\n')
print(f"Total lines: {len(lines)}")

import re

for i, line in enumerate(lines):
    line_stripped = line.strip()
    section_match = re.match(r'^([A-Z])\.\s+(.+)?$', line_stripped)
    if section_match:
        print(f"Line {i}: Found section {section_match.group(1)} - '{line_stripped[:50]}...'")
    elif line_stripped:
        print(f"Line {i}: '{line_stripped[:50]}...'")

print("\nTrying coordinate extraction...")
try:
    from downloaders.navwarnings_parser import extract_sectioned_coordinates
    coord_sets = extract_sectioned_coordinates(davis_warning)
    print(f"Result: {coord_sets}")
except Exception as e:
    print(f"Exception: {e}")
    import traceback
    traceback.print_exc()