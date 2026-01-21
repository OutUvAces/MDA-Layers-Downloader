#!/usr/bin/env python3

# Test just the Davis Strait warning to see if the boundary detection works

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

from downloaders.navwarnings_parser import extract_sectioned_coordinates

coord_sets = extract_sectioned_coordinates(davis_warning)

print(f"Found {len(coord_sets)} coordinate sets")

for i, coord_set in enumerate(coord_sets):
    print(f"\nSet {i}: {coord_set[0]}")
    if len(coord_set) >= 3:
        feature_text = coord_set[2]
        print(f"Feature text: {repr(feature_text)}")

from downloaders.navigation_warnings import extract_feature_description

if coord_sets:
    result = extract_feature_description(davis_warning, coord_sets, coord_sets[0])
    print("\nFeature A description (first 200 chars):")
    print(result[:200] + "...")