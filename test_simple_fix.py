#!/usr/bin/env python3

# Test the simpler fix: detect last feature and strip post-coordinate info

multi_warning = """HYDROPAC 3475/25(63).
BAY OF BENGAL.
BANGLADESH.
DNC 03.
HAZARDOUS OPERATIONS 0001Z TO 1600Z
DAILY 01 THRU 31 JAN 26 IN AREAS BOUND BY:
A. 21-20.83N 091-28.00E, 21-41.00N 091-14.00E,
21-20.83N 090-34.00E, 21-00.00N 090-47.83E.
B. 20-22.00N 091-06.00E, 20-07.00N 090-52.00E,
19-44.00N 091-21.00E, 20-00.00N 091-36.00E.
CANCEL THIS MSG 311700Z JAN 26.
280033Z DEC 25"""

print("Testing simpler fix - strip post-info from last feature:")
print("=" * 60)
print()

from downloaders.navwarnings_parser import extract_sectioned_coordinates
from downloaders.navigation_warnings import extract_feature_description

coord_sets = extract_sectioned_coordinates(multi_warning)

print("Extracted coordinate sets:")
for i, coord_set in enumerate(coord_sets):
    print(f"Set {i}: {coord_set[0]}")
    if len(coord_set) >= 3:
        print(f"  Feature text: {repr(coord_set[2])}")
print()

if coord_sets:
    print("Feature descriptions:")
    for i, coord_set in enumerate(coord_sets):
        result = extract_feature_description(multi_warning, coord_sets, coord_set)
        print(f"Area {chr(65+i)}:")
        print(result)
        print("-" * 40)
        print()