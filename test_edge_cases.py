#!/usr/bin/env python3

# Test edge cases for the boundary detection approach

# Test case 1: Features not separated by line breaks
print("=== Test Case 1: Features on same line ===")
warning1 = """HAZARDOUS OPERATIONS IN AREAS BOUND BY: A. 10-00N 020-00E, 10-00N 025-00E B. 15-00N 020-00E, 15-00N 025-00E CANCEL THIS MSG"""

from downloaders.navwarnings_parser import extract_sectioned_coordinates

coord_sets1 = extract_sectioned_coordinates(warning1)
print(f"Warning: {warning1}")
if coord_sets1:
    print(f"Found {len(coord_sets1)} coordinate sets")
    for i, coord_set in enumerate(coord_sets1):
        print(f"  Set {i}: {coord_set[0]} - {repr(coord_set[2][:50])}...")
else:
    print("No coordinate sets found")
    # Debug: check what the function sees
    lines = warning1.split('\n')
    print(f"Lines: {lines}")
    for i, line in enumerate(lines):
        import re
        section_match = re.match(r'^([A-Z])\.\s+(.+)?$', line.strip())
        if section_match:
            print(f"Found section marker on line {i}: {section_match.groups()}")

# Test case 2: Features with mixed content
print("\n=== Test Case 2: Features with mixed content ===")
warning2 = """WARNING: A. Position 10-00N 020-00E with depth 50 meters and equipment. Contact info: phone 123-456. B. Position 15-00N 025-00E with depth 60 meters. General contact: email@example.com"""

coord_sets2 = extract_sectioned_coordinates(warning2)
print(f"Warning: {warning2}")
print(f"Found {len(coord_sets2)} coordinate sets")
for i, coord_set in enumerate(coord_sets2):
    print(f"  Set {i}: {coord_set[0]} - {repr(coord_set[2][:50])}...")

# Test case 3: What happens with the Davis Strait warning boundary detection
print("\n=== Test Case 3: Davis Strait boundary analysis ===")
davis_warning = """NAVAREA IV 1292/25(15).
DAVIS STRAIT.
22 OCEAN BOTTOM MOORINGS DEPLOYED
ONE METER ABOVE OCEAN FLOOR UNTIL
FURTHER NOTICE, IN:
A. 61-32.92N 059-23.18W 2230 METERS.
B. 61-20.01N 058-47.40W 2545 METERS.
V. 60-13.29N 058-33.87W 2635 METERS.
ANY INQUIRIES CAN BE DIRECTED TO GRAEME
CAIRNS AT NFSI (GRAEME.CAIRNS@DAL.CA)"""

coord_sets3 = extract_sectioned_coordinates(davis_warning)
print(f"Found {len(coord_sets3)} coordinate sets")

# Analyze what each section includes
lines = davis_warning.split('\n')
for i, coord_set in enumerate(coord_sets3):
    print(f"\nSet {i} ({coord_set[0]}):")
    print(f"  Feature text: {repr(coord_set[2])}")

    # Find which lines this corresponds to
    for j, (line_idx, label, start_content) in enumerate([]):  # Would need to re-extract positions
        pass  # Skip for now

print("\n=== Analysis ===")
print("Current approach assumes line-based separation.")
print("For features on same line, it may not work correctly.")
print("For mixed content, it may include too much or too little.")