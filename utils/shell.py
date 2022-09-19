import os
import sys
import readline
import code

sys.path.append(
    os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
)

from fame.core import fame_init  # noqa: E402

fame_init()

shell = code.InteractiveConsole()
shell.interact()
