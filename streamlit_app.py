"""
Streamlit entrypoint at the root of the repository.
Delegates to app/presentation/ui.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Now import the main function from ui.py and run it
from app.presentation.ui import main

if __name__ == "__main__":
    main()
