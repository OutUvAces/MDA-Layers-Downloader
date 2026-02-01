---
name: guiapptestingguidance
description: This is a new rule
---

# Overview

## General Principles
- You are helping develop a desktop application with a graphical user interface (GUI). The core application logic must be separable from the GUI code.
- Never suggest or attempt to run the main application entry point (e.g., the script that launches the GUI window). The agent cannot interact with or observe graphical interfaces.
- Always separate business logic, data processing, and core functionality from GUI-specific code. Keep GUI code minimal and focused only on presentation and user interaction.

## Testing Strategy (MANDATORY)
- For any new feature, bug fix, or code change, ALWAYS write independent test scripts or test functions that can be executed in the terminal/console and produce visible text output.
- Preferred testing approaches (in order of priority):
  1. Pure unit tests using assertions and print statements to show results.
  2. Small standalone test scripts that import and exercise specific functions/classes without launching the GUI.
  3. If needed, use simple mocking of GUI dependencies (e.g., mock user inputs with hardcoded values).
- Test scripts must:
  - Run entirely in the console.
  - Print clear, readable output (e.g., "Test passed: expected X, got X").
  - Use print() statements liberally to show intermediate results and final outcomes.
  - Include a main guard (if __name__ == "__main__":) so they can be run directly with `python test_script.py`.
- When verifying or debugging code, propose and write these test scripts first. Only consider the code correct after the tests pass with visible console output.
- Never assume code works based on "it should work" reasoning — always require runnable tests with observable results.

## Code Style & Structure
- Organize the project with clear separation:
  - Core logic in modules like `core.py`, `utils.py`, etc.
  - GUI code isolated in `gui.py` or `main.py`.
  - Tests in a `tests/` folder or as separate `test_*.py` files.
- Use descriptive function and variable names.
- Add concise docstrings and comments only where behavior is non-obvious.
- Prefer readable, maintainable code over clever one-liners.