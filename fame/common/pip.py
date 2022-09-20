import sys
import subprocess


def pip_install(*args):
    try:
        subprocess.check_output(
            [sys.executable, "-m", "pip", "install"] + list(args),
            stderr=subprocess.STDOUT,
        )

        return 0, ""
    except subprocess.CalledProcessError as e:
        return e.returncode, e.output
