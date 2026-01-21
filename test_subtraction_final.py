#!/usr/bin/env python3

# Test the corrected subtraction approach using existing coordinate extraction logic
romanian_warning = """DUE TO THE PRESENCE OF MINES, ALL VESSELS
APPROACHING AND DEPARTING ROMANIAN PORTS ARE
ENCOURAGED TO USE THE FOLLOWING RECOMMNEDED
TRACKS:
A. PORT OF MANGALIA ALONG TRACKLINE JOINING
43-47.59N 028-50.86E, 43-47.50N 028-37.61E.
B. PORT OF NAVODARI ALONG TRAKLINE JOINING
43-47.59N 028-50.86E, 44-11.33N 028-50.86E,
44-15.52N 028-45.04E.
C. ENTRANCE TO PORT OF CONSTANTA TRAFFIC
SEPERATION SCHEME ALONG TRACKLINE JOINING
43-47.59N 028-50.86E, 43-58.79N 028-50.86E."""

# These coordinate sets come from the existing extract_sectioned_coordinates() function
# which already used regex to identify the A., B., C. sections
all_coord_sets = [
    ['TRACKLINE_A', [[43.793166666666664, 28.847666666666665], [43.791666666666664, 28.626833333333334]], 'A. PORT OF MANGALIA ALONG TRACKLINE JOINING 43-47.59N 028-50.86E, 43-47.50N 028-37.61E.'],
    ['TRACKLINE_B', [[43.793166666666664, 28.847666666666665], [44.188833333333335, 28.847666666666665], [44.25866666666667, 28.750666666666667]], 'B. PORT OF NAVODARI ALONG TRAKLINE JOINING 43-47.59N 028-50.86E, 44-11.33N 028-50.86E, 44-15.52N 028-45.04E.'],
    ['TRACKLINE_C', [[43.793166666666664, 28.847666666666665], [43.97983333333333, 28.847666666666665]], 'C. ENTRANCE TO PORT OF CONSTANTA TRAFFIC SEPERATION SCHEME ALONG TRACKLINE JOINING 43-47.59N 028-50.86E, 43-58.79N 028-50.86E.']
]

from downloaders.navigation_warnings import extract_feature_description

print("Testing subtraction approach using existing coordinate extraction:")
print("Full warning:")
print(romanian_warning)
print()

print("Each coord_set already has feature text identified by existing regex algorithms:")
for i, coord_set in enumerate(all_coord_sets):
    print(f"  Feature {chr(65+i)}: {coord_set[2][:60]}...")
print()

# Test extraction for each feature using the subtraction method
for i, coord_set in enumerate(all_coord_sets):
    feature_desc = extract_feature_description(romanian_warning, all_coord_sets, coord_set)
    print(f"Feature {chr(65+i)} Result:")
    print(feature_desc)
    print("=" * 80)
    print()