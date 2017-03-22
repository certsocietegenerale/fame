import sys
from StringIO import StringIO


class RedirectedOutput:
    def __init__(self):
        self.output = StringIO()
        self.old_stdout = sys.stdout
        self.old_stderr = sys.stderr
        sys.stdout = sys.stderr = self.output

    def restore(self):
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr

        return self.output.getvalue()
