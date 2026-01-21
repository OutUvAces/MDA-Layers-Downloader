#!/usr/bin/env python3

# Debug the subtraction approach
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
all_coord_sets = [
    ['TRACKLINE_A', [[43.793166666666664, 28.847666666666665], [43.791666666666664, 28.626833333333334]], 'A. PORT OF MANGALIA ALONG TRACKLINE JOINING 43-47.59N 028-50.86E, 43-47.50N 028-37.61E.'],
    ['TRACKLINE_B', [[43.793166666666664, 28.847666666666665], [44.188833333333335, 28.847666666666665], [44.25866666666667, 28.750666666666667]], 'B. PORT OF NAVODARI ALONG TRAKLINE JOINING 43-47.59N 028-50.86E, 44-11.33N 028-50.86E, 44-15.52N 028-45.04E.'],
    ['TRACKLINE_C', [[43.793166666666664, 28.847666666666665], [43.97983333333333, 28.847666666666665]], 'C. ENTRANCE TO PORT OF CONSTANTA TRAFFIC SEPERATION SCHEME ALONG TRACKLINE JOINING 43-47.59N 028-50.86E, 43-58.79N 028-50.86E.']
]

print("=== DEBUGGING SUBTRACTION APPROACH ===")
print("Full warning text:")
print(repr(romanian_warning))
print()

print("Feature texts from coord_sets:")
for i, coord_set in enumerate(all_coord_sets):
    print(f"Feature {chr(65+i)}: {repr(coord_set[2])}")
    print(f"  In full text? {coord_set[2] in romanian_warning}")
    print()

# Test individual subtractions
common_text = romanian_warning
print("Starting with full text, subtracting each feature...")

for i, coord_set in enumerate(all_coord_sets):
    if len(coord_set) >= 3:
        other_feature_text = coord_set[2].strip()
        print(f"Removing Feature {chr(65+i)}: {repr(other_feature_text)}")
        print(f"  Before: {len(common_text)} chars")

        import re
        escaped_text = re.escape(other_feature_text)
        common_text = re.sub(escaped_text, '', common_text, flags=re.IGNORECASE)

        print(f"  After: {len(common_text)} chars")
        print(f"  Result: {repr(common_text)}")
        print()

print("Final common text:")
print(repr(common_text))