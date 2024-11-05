# based on https://gist.github.com/bbarker/4ddf4a1c58ae8465f3d37b6f2234a421

import os
import subprocess
import sys
import unittest
from typing import List


class MyPyTest(unittest.TestCase):

    def __call_mypy__(self, args, files):
        result: int = subprocess.call(self.base_mypy_call + args + files, env=os.environ, cwd=self.pypath)
        self.assertEqual(result, 0, '')

    def test_run_mypy_app(self):
        mypy_args: List[str] = [
            "--disable-error-code", "var-annotated"
        ]
        self.__call_mypy__(mypy_args, ["main.py"])

    # Run test again, but without disabling any error codes.
    # This is expected to fail, but we intentionally keep this test around to
    #   1) try not to add any more errors to what's already in the baseline
    #   2) as a reminder to try to move the codebase towards having type checking eventually
    @unittest.expectedFailure
    def test_run_strict_mypy_app(self):
        mypy_args: List[str] = []
        self.__call_mypy__(mypy_args, ["main.py"])

    def __init__(self, *args, **kwargs) -> None:
        super(MyPyTest, self).__init__(*args, **kwargs)
        my_env = os.environ.copy()
        self.pypath: str = my_env.get("PYTHONPATH", os.getcwd())
        self.base_mypy_call: List[str] = [sys.executable, "-m", "mypy", "--ignore-missing-imports"]


if __name__ == '__main__':
    unittest.main()
