#!/usr/bin/env python3

# Test the correct approach: identify common text before/after features

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

print("Testing correct approach - common text before/after features:")
print("=" * 70)
print()

from downloaders.navwarnings_parser import extract_sectioned_coordinates
from downloaders.navigation_warnings import extract_feature_description

coord_sets = extract_sectioned_coordinates(multi_warning)

print("Individual features identified by existing regex:")
for i, coord_set in enumerate(coord_sets):
    print(f"Feature {chr(65+i)}: {coord_set[2][:60]}...")
print()

print("Common text identification:")
import re

# Common text before first feature
first_match = re.search(r'\b[A-Z]\.\s+', multi_warning)
common_before = multi_warning[:first_match.start()].strip() if first_match else ""
print(f"Before first feature: '{common_before}'")

# Common text after last feature
coord_pattern = r'\b\d{2,3}-\d{2}\.\d{1,2}[EW]\b'
coords = list(re.finditer(coord_pattern, multi_warning))
common_after = ""
if coords:
    last_coord_end = coords[-1].end()
    if last_coord_end < len(multi_warning):
        common_after = multi_warning[last_coord_end:].strip()
print(f"After last feature: '{common_after}'")
print()

print("Feature descriptions (common_before + feature_text + common_after):")
for i, coord_set in enumerate(coord_sets):
    result = extract_feature_description(multi_warning, coord_sets, coord_set)
    print(f"Area {chr(65+i)}:")
    print(result)
    print("-" * 50)
    print()