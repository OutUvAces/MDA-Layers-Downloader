#!/usr/bin/env python3

# Debug the duplicate post-coordinate issue

warning_text = """HYDROPAC 114/26(63). ANDAMAN SEA. BAY OF BENGAL. INDIA. DNC 03. HAZARDOUS OPERATIONS 0230Z TO 1230Z DAILY 20 THRU 24 JAN IN AREAS BOUND BY:
B. 09-23.58N 093-19.40E, 08-29.42N 094-02.57E, 08-07.90N 093-39.83E, 08-15.40N 093-32.42E, 08-57.12N 092-44.78E. CANCEL THIS MSG 241330Z JAN 26. 140608Z JAN 26

CANCEL THIS MSG 241330Z JAN 26. 140608Z JAN 26"""

print("Raw warning text:")
print(repr(warning_text))
print()

# Mock coordinate sets (only one area B)
all_coord_sets = [
    ['BOUNDARY_AREA_B', [[9.3930, 93.3233], [8.4903, 94.0438], [8.1317, 93.6638], [8.2567, 93.5403], [8.9520, 92.7463]], 'B. 09-23.58N 093-19.40E, 08-29.42N 094-02.57E, 08-07.90N 093-39.83E, 08-15.40N 093-32.42E, 08-57.12N 092-44.78E.']
]

print("Coord set feature text:")
print(repr(all_coord_sets[0][2]))
print()

from downloaders.navigation_warnings import extract_feature_description

print("Testing extraction:")
result = extract_feature_description(warning_text, all_coord_sets, all_coord_sets[0])
print("Result:")
print(repr(result))
print()

print("Pretty result:")
print(result)
print()

# Let's debug the subtraction step by step
import re

normalized_full_text = re.sub(r'\s+', ' ', warning_text).strip()
print("Normalized full text:")
print(repr(normalized_full_text))
print()

feature_text = all_coord_sets[0][2].strip()
print("Feature text to remove:")
print(repr(feature_text))
print()

common_text = normalized_full_text
escaped_text = re.escape(feature_text)
common_text = re.sub(escaped_text, '', common_text, flags=re.IGNORECASE)

print("After removing feature text:")
print(repr(common_text))
print()

# Clean up
common_text = common_text.strip()
common_text = re.sub(r'\b[A-Z]\.\s+', '', common_text)
common_text = re.sub(r'\s+', ' ', common_text)
common_text = re.sub(r'\s*:\s*', ': ', common_text)
common_text = common_text.strip()

print("After cleanup:")
print(repr(common_text))
print()

final_result = f"{common_text}: {feature_text}" if not common_text.endswith(':') else f"{common_text} {feature_text}"
print("Final result:")
print(repr(final_result))