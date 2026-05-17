import sys
sys.path.insert(0, '.')
from tests.test_core import *
import unittest
unittest.main(module='tests.test_core', argv=['run_tests.py'])
