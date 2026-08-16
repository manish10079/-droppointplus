"""PyInstaller entry point for DropPoint+.

``droppointplus/main.py`` uses relative imports (``from .app_config import
...``), which fail when PyInstaller executes a script as ``__main__`` with no
package context. This launcher sits at the project root and imports the
package absolutely, so the frozen app boots cleanly.

Run::

    pyinstaller --windowed --name DropPointPlus launcher.py
"""

import sys

from droppointplus.main import main

if __name__ == "__main__":
    sys.exit(main())
