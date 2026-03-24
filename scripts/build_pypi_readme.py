import os

with open("README.md", "r", encoding="utf-8") as f:
    lines = f.readlines()

out_lines = []
for i, line in enumerate(lines):
    if i == 0 and ("English" in line or "Chinese" in line):
        continue
    # Skip the empty line following the toggle banner if it exists
    if i == 1 and line.strip() == "":
        continue
    
    out_lines.append(line)
    
    # Insert the redirect link after the # title
    if line.startswith("# Project Aegis"):
        out_lines.append("\n> **Note**: This is the PyPI published documentation. For the full architecture diagrams, real UI screenshots, and the **Chinese translation (繁體中文版)**, please visit the [GitHub Repository](https://github.com/TPEmist/project-aegis).\n")

with open("README.pypi.md", "w", encoding="utf-8") as f:
    f.writelines(out_lines)

print("Generated README.pypi.md")
