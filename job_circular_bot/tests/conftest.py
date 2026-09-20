"""Test configuration.

Makes the modules under src/ importable (the bot is not a package, it is a
folder of scripts run directly), and nothing else.
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
