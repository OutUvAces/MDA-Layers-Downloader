#!/usr/bin/env python3

# Debug the boundary detection

davis_warning = """NAVAREA IV 1292/25(15).
DAVIS STRAIT.
22 OCEAN BOTTOM MOORINGS DEPLOYED
ONE METER ABOVE OCEAN FLOOR UNTIL
FURTHER NOTICE, IN:
A. 61-32.92N 059-23.18W 2230 METERS.
B. 61-20.01N 058-47.40W 2545 METERS.
C. 61-03.97N 058-12.11W 2733 METERS.
D. 60-51.41N 057-37.03W 2882 METERS.
E. 61-25.56N 059-50.90W 2053 METERS.
F. 61-15.38N 059-22.43W 2310 METERS.
G. 61-03.18N 058-55.91W 2519 METERS.
H. 60-53.82N 058-33.22W 2650 METERS.
I. 60-38.79N 058-04.73W 2678 METERS.
J. 61-09.01N 060-06.80W 2056 METERS.
K. 61-02.04N 059-32.47W 2335 METERS.
L. 60-49.16N 059-12.67W 2383 METERS.
M. 60-43.09N 058-43.89W 2442 METERS.
N. 60-50.62N 060-11.91W 1963 METERS.
O. 60-42.99N 059-40.96W 2093 METERS.
P. 60-35.80N 059-10.90W 2231 METERS.
Q. 60-28.94N 058-27.74W 2613 METERS.
R. 60-14.23N 057-51.33W 2772 METERS.
S. 60-35.36N 060-10.70W 1739 METERS.
T. 60-23.71N 059-36.23W 2257 METERS.
U. 60-18.96N 059-04.37W 2428 METERS.
V. 60-13.29N 058-33.87W 2635 METERS.
ANY INQUIRIES CAN BE DIRECTED TO GRAEME
CAIRNS AT NFSI (GRAEME.CAIRNS@DAL.CA) OR
ALEXANDRE PLOURDE AT NRCAN
(ALEXANDRE.PLOURDE@NRCAN-RNCAN.GC.CA).
191207Z NOV 25"""

print("Analyzing section boundaries:")
lines = davis_warning.split('\n')

# Find all section markers
section_positions = []
for i, line in enumerate(lines):
    line_stripped = line.strip()
    import re
    section_match = re.match(r'^([A-Z])\.\s+(.+)?$', line_stripped)
    if section_match:
        label = section_match.group(1)
        section_positions.append((i, label, section_match.group(2) or ""))

print(f"Found {len(section_positions)} sections:")
for i, (line_idx, label, content) in enumerate(section_positions):
    print(f"  {label} at line {line_idx}: {repr(content[:50])}...")
    if i < len(section_positions) - 1:
        next_line_idx = section_positions[i + 1][0]
        print(f"    Next section starts at line {next_line_idx}")
        print(f"    So {label} should end at line {next_line_idx - 1}")
        # Show what would be included
        end_line = next_line_idx - 1
        included_lines = []
        for k in range(line_idx, end_line + 1):
            included_lines.append(lines[k].strip())
        combined = ' '.join(included_lines)
        print(f"    Would include: {repr(combined[:100])}...")
    else:
        print(f"    This is the last section")
        print(f"    Lines from {line_idx} to end:")
        included_lines = []
        for k in range(line_idx, len(lines)):
            included_lines.append(lines[k].strip())
        combined = ' '.join(included_lines)
        print(f"    Would include: {repr(combined[:100])}...")

print("\nThe issue is that the last section includes everything until the end of the text.")
print("We need to stop the last section at the last coordinate, not include contact info.")