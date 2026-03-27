"""Thin re-import shim — tests have been split into test_py_nav.py, test_js_nav.py, and test_tf_nav.py."""

from tests.navigation.test_js_nav import *  # noqa: F401,F403
from tests.navigation.test_py_nav import *  # noqa: F401,F403
from tests.navigation.test_tf_nav import *  # noqa: F401,F403
