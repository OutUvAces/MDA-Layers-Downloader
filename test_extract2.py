warning_text = """NAVAREA: XII
Warning: NAV001/26
Category: Danger

Description:
HAZARDOUS OPERATIONS, SPACE DEBRIS:
A. 150825Z TO 150855Z JAN, ALTERNATE
170001Z TO 222210Z JAN IN AREA
WITHIN NINE MILES OF 33-40.72N 119-09.16W.
B. 150825Z TO 150855Z JAN, ALTERNATE
162350Z TO 222200Z JAN IN AREA
WITHIN NINE MILES OF 33-00.72N 117-44.88W.
C. 150825Z TO 150855Z JAN, ALTERNATE
170740Z TO 222155Z JAN IN AREA
WITHIN NINE MILES OF 32-36.18N 117-42.27W.
D. 150825Z TO 150855Z JAN, ALTERNATE
162350Z TO 222210Z JAN IN AREA BOUND BY
19-48.00N 134-48.00W, 17-06.00N 131-48.00W,
28-18.00N 121-54.00W, 29-54.00N 124-24.00W.
E. 150825Z TO 150855Z JAN, ALTERNATE
162350Z TO 222210Z JAN IN AREA BOUND BY
46-00.00N 135-42.00W, 44-48.00N 139-00.00W,
37-12.00N 124-54.00W, 37-30.00N 123-42.00W,
38-36.00N 124-12.00W.
"""

from downloaders.navigation_warnings import extract_warning_components
from downloaders.navwarnings_parser import extract_coordinates_from_text

prefix, feature_list, suffix = extract_warning_components(warning_text)
coords = extract_coordinates_from_text(warning_text)

print("PREFIX:", repr(prefix))
print("NUM FEATURES:", len(feature_list))
print("FEATURES:")
for i, f in enumerate(feature_list[:2] + feature_list[-2:]):  # First/last 2
    print(f"  {i}: {repr(f)}")
print("SUFFIX:", repr(suffix))
print("\nCOORDS:")
print(repr(coords))
