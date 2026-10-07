"""Clean all API keys from scripts — replace with os.environ.get() calls."""
import re, os
from pathlib import Path

SCRIPTS_DIR = Path("/home/z/my-project/scripts")

# Patterns to replace
GLM_KEY = os.environ.get("GLM_KEY", "")
COMPOSIO_KEY = os.environ.get("COMPOSIO_KEY", "")

# Find all .py files with keys
files_to_clean = []
for p in SCRIPTS_DIR.glob("*.py"):
    content = p.read_text()
    if GLM_KEY in content or COMPOSIO_KEY in content:
        files_to_clean.append(p)

print(f"Found {len(files_to_clean)} files to clean:")
for p in files_to_clean:
    print(f"  - {p.name}")

# Clean each file
for p in files_to_clean:
    content = p.read_text()
    original = content
    
    # Replace GLM key — handle various patterns
    # Pattern 1: GLM_KEY = "82965..."
    content = re.sub(
        rf'GLM_KEY\s*=\s*["\']{re.escape(GLM_KEY)}["\']',
        'GLM_KEY = os.environ.get("GLM_KEY", "")',
        content
    )
    # Pattern 2: GLM_KEY = os.environ.get("GLM_KEY", "") (already handled above)
    
    # Replace Composio key
    content = re.sub(
        rf'COMPOSIO_KEY\s*=\s*["\']{re.escape(COMPOSIO_KEY)}["\']',
        'COMPOSIO_KEY = os.environ.get("COMPOSIO_KEY", "")',
        content
    )
    
    # Replace KEY = "ak_..." (in test_composio.py)
    content = re.sub(
        rf'KEY\s*=\s*["\']{re.escape(COMPOSIO_KEY)}["\']',
        'KEY = os.environ.get("COMPOSIO_KEY", "")',
        content
    )
    
    # Add `import os` at the top if not already present and we made substitutions
    if content != original:
        if "import os" not in content.split("\n")[:20]:
            # Add after the first docstring or at the very top
            lines = content.split("\n")
            insert_at = 0
            # Skip docstring
            if lines and lines[0].startswith('"""'):
import os
                for i, line in enumerate(lines[1:], 1):
                    if '"""' in line:
                        insert_at = i + 1
                        break
            lines.insert(insert_at, "import os")
            content = "\n".join(lines)
        
        p.write_text(content)
        print(f"  ✓ Cleaned {p.name}")
    else:
        print(f"  - No changes needed for {p.name} (patterns may differ)")

# Verify no keys remain
print("\n=== Verification ===")
for p in files_to_clean:
    content = p.read_text()
    if GLM_KEY in content:
        print(f"  ⚠ {p.name} STILL HAS GLM KEY")
    if COMPOSIO_KEY in content:
        print(f"  ⚠ {p.name} STILL HAS COMPOSIO KEY")

# Final grep across all scripts
print("\n=== Final scan of all scripts ===")
import subprocess
result = subprocess.run(
    ["grep", "-rl", GLM_KEY, str(SCRIPTS_DIR)],
    capture_output=True, text=True
)
if result.stdout.strip():
    print(f"⚠ GLM key still in: {result.stdout.strip()}")
else:
    print("✓ No GLM keys in any script")

result = subprocess.run(
    ["grep", "-rl", COMPOSIO_KEY, str(SCRIPTS_DIR)],
    capture_output=True, text=True
)
if result.stdout.strip():
    print(f"⚠ Composio key still in: {result.stdout.strip()}")
else:
    print("✓ No Composio keys in any script")
