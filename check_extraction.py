#!/usr/bin/env python3

# Check what the actual coordinate extraction produces for this warning

warning_text = """HYDROPAC 114/26(63). ANDAMAN SEA. BAY OF BENGAL. INDIA. DNC 03. HAZARDOUS OPERATIONS 0230Z TO 1230Z DAILY 20 THRU 24 JAN IN AREAS BOUND BY:
B. 09-23.58N 093-19.40E, 08-29.42N 094-02.57E, 08-07.90N 093-39.83E, 08-15.40N 093-32.42E, 08-57.12N 092-44.78E. CANCEL THIS MSG 241330Z JAN 26. 140608Z JAN 26

CANCEL THIS MSG 241330Z JAN 26. 140608Z JAN 26"""

print("Raw warning text:")
print(repr(warning_text))
print()

from downloaders.navwarnings_parser import extract_sectioned_coordinates

coord_sets = extract_sectioned_coordinates(warning_text)

print("Extracted coordinate sets:")
for i, coord_set in enumerate(coord_sets):
    print(f"Set {i}: {coord_set}")
    if len(coord_set) >= 3:
        print(f"  Feature text: {repr(coord_set[2])}")
print()

if coord_sets:
    from downloaders.navigation_warnings import extract_feature_description

    print("Testing feature description extraction:")
    result = extract_feature_description(warning_text, coord_sets, coord_sets[0])
    print("Result:")
    print(result)