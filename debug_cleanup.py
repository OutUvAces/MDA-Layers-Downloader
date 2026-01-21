#!/usr/bin/env python3

# Debug the cleanup logic

feature_text = 'V. 60-13.29N 058-33.87W 2635 METERS. ANY INQUIRIES CAN BE DIRECTED TO GRAEME CAIRNS AT NFSI (GRAEME.CAIRNS@DAL.CA) OR ALEXANDRE PLOURDE AT NRCAN (ALEXANDRE.PLOURDE@NRCAN-RNCAN.GC.CA). 191207Z NOV 25'

print("Original feature text:")
print(repr(feature_text))
print()

import re

# Test each pattern
post_info_patterns = [
    r'\bCANCEL\s+THIS\s+MSG\b.*$',
    r'\b\d{6}Z\s+\w{3}\s+\d{2}\b.*$',  # Timestamp like "280033Z DEC 25"
    r'\bANY\s+INQUIRIES\b.*$',  # Contact info like "ANY INQUIRIES CAN BE DIRECTED"
    r'\bCONTACT\b.*$',
    r'\bTELEPHONE\b.*$',
    r'\bEMAIL\b.*$'
]

for i, pattern in enumerate(post_info_patterns):
    print(f"Testing pattern {i}: {pattern}")
    match = re.search(pattern, feature_text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
    if match:
        print(f"  MATCH at position {match.start()}-{match.end()}")
        print(f"  Matched text: {repr(match.group())}")
        cleaned = feature_text[:match.start()].strip()
        print(f"  Would clean to: {repr(cleaned)}")
        break
    else:
        print("  No match")
print()

# Test the actual cleanup
cleaned_text = feature_text
for pattern in post_info_patterns:
    match = re.search(pattern, cleaned_text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
    if match:
        cleaned_text = cleaned_text[:match.start()].strip()
        print(f"Applied pattern: {pattern}")
        print(f"Cleaned to: {repr(cleaned_text)}")
        break

print(f"\nFinal result: {repr(cleaned_text)}")