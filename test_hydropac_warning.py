#!/usr/bin/env python3

# Test the subtraction approach with the HYDROPAC warning that has both pre- and post-list information

hydropac_warning = """HYDROPAC 3475/25(63).
BAY OF BENGAL.
BANGLADESH.
DNC 03.
HAZARDOUS OPERATIONS 0001Z TO 1600Z
DAILY 01 THRU 31 JAN 26 IN AREAS BOUND BY:
A. 21-20.83N 091-28.00E, 21-41.00N 091-14.00E,
21-20.83N 090-34.00E, 21-00.00N 090-47.83E.
B. 20-22.00N 091-06.00E, 20-07.00N 090-52.00E,
19-44.00N 091-21.00E, 20-00.00N 091-36.00E.
C. 20-24.00N 091-59.00E, 20-46.50N 091-31.00E,
20-22.00N 091-06.00E, 20-00.00N 091-36.00E.
D. 21-18.00N 089-50.00E, 21-18.00N 089-31.00E,
21-04.00N 089-34.00E, 21-04.00N 089-54.00E.
E. 20-58.00N 089-54.00E, 20-58.00N 089-34.00E,
20-34.00N 089-34.00E, 20-34.00N 089-54.00E.
CANCEL THIS MSG 311700Z JAN 26.
280033Z DEC 25"""

print("Testing HYDROPAC warning with pre- and post-list information:")
print("=" * 80)
print(hydropac_warning)
print("=" * 80)
print()

# Mock coordinate sets that would come from extract_sectioned_coordinates
# These represent the 5 areas A through E
all_coord_sets = [
    ['BOUNDARY_AREA_A', [[21.3472, 91.4667], [21.6833, 91.2333], [21.3472, 90.5667], [21.0, 90.7972]], 'A. 21-20.83N 091-28.00E, 21-41.00N 091-14.00E, 21-20.83N 090-34.00E, 21-00.00N 090-47.83E.'],
    ['BOUNDARY_AREA_B', [[20.3667, 91.1], [20.1167, 90.8667], [19.7333, 91.35], [20.0, 91.6]], 'B. 20-22.00N 091-06.00E, 20-07.00N 090-52.00E, 19-44.00N 091-21.00E, 20-00.00N 091-36.00E.'],
    ['BOUNDARY_AREA_C', [[20.4, 91.9833], [20.775, 91.5167], [20.3667, 91.1], [20.0, 91.6]], 'C. 20-24.00N 091-59.00E, 20-46.50N 091-31.00E, 20-22.00N 091-06.00E, 20-00.00N 091-36.00E.'],
    ['BOUNDARY_AREA_D', [[21.3, 89.8333], [21.3, 89.5167], [21.0667, 89.5667], [21.0667, 89.9]], 'D. 21-18.00N 089-50.00E, 21-18.00N 089-31.00E, 21-04.00N 089-34.00E, 21-04.00N 089-54.00E.'],
    ['BOUNDARY_AREA_E', [[20.9667, 89.9], [20.9667, 89.5667], [20.5667, 89.5667], [20.5667, 89.9]], 'E. 20-58.00N 089-54.00E, 20-58.00N 089-34.00E, 20-34.00N 089-34.00E, 20-34.00N 089-54.00E.']
]

from downloaders.navigation_warnings import extract_feature_description

print("Testing extraction for each area:")
print()

for i, coord_set in enumerate(all_coord_sets):
    feature_desc = extract_feature_description(hydropac_warning, all_coord_sets, coord_set)
    print(f"Area {chr(65+i)}:")
    print(feature_desc)
    print("-" * 80)
    print()

# Test with a few other NAV areas and categories
print("Testing with other NAV areas and categories...")
print("=" * 80)

# Test HYDROLANT ice warning
ice_warning = """NAVAREA IV 190/25(15).
LABRADOR SEA.
CANADA
ICE CONTROL ZONE TANGO (T) HAS BEEN FULLY ACTIVATED
AND DECLARED IN FORCE BY CANADIAN AUTHORITIES.
ALL LADEN OIL TANKERS AND SHIPS CARRYING CHEMICALS IN
BULK SHOULD COMPLY WITH TRANSPORT CANADA'S TP 15163.
130304Z FEB 25"""

ice_coord_sets = [
    ['POINT_ICE_ZONE', [[56.6833, -53.2715]], 'ICE CONTROL ZONE TANGO (T) HAS BEEN FULLY ACTIVATED AND DECLARED IN FORCE BY CANADIAN AUTHORITIES.']
]

print("HYDROLANT Ice Warning:")
ice_desc = extract_feature_description(ice_warning, ice_coord_sets, ice_coord_sets[0])
print(ice_desc)
print()

# Test NAVAREA XII military warning
military_warning = """HYDROPAC 3473/25(97).
NORTH PACIFIC.
DNC 12.
GUNNERY EXERCISES 2300Z TO 0900Z DAILY
31 DEC THRU 30 JAN 26 IN AREA BOUND BY
28-15.15N 146-29.47E, 27-55.15N 144-57.48E,
25-00.16N 145-35.48E, 25-25.16N 147-37.47E.
CANCEL THIS MSG 311000Z JAN 26.
262139Z DEC 25"""

military_coord_sets = [
    ['BOUNDARY_AREA_GUNNERY', [[28.2525, 146.4912], [27.9192, 144.9580], [25.0027, 145.5913], [25.4193, 147.6245]], '28-15.15N 146-29.47E, 27-55.15N 144-57.48E, 25-00.16N 145-35.48E, 25-25.16N 147-37.47E.']
]

print("HYDROPAC Military Warning:")
military_desc = extract_feature_description(military_warning, military_coord_sets, military_coord_sets[0])
print(military_desc)
print()

print("✅ All tests completed!")