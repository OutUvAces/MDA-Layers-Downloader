#!/usr/bin/env python3

# Simple test of Davis Strait coordinate extraction

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

print("Testing coordinate extraction only...")

from downloaders.navwarnings_parser import extract_sectioned_coordinates

try:
    coord_sets = extract_sectioned_coordinates(davis_warning)
    if coord_sets:
        print(f"Success: Found {len(coord_sets)} coordinate sets")
        for i, coord_set in enumerate(coord_sets):
            print(f"  {i}: {coord_set[0]}")
    else:
        print("No coordinate sets found")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()