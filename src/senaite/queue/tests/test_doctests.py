import doctest
from os.path import join

import unittest2 as unittest
from Testing import ZopeTestCase as ztc
from pkg_resources import resource_listdir
from senaite.queue import PRODUCT_NAME
from senaite.queue.tests.base import SimpleTestCase

# Option flags for doctests
flags = doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE | doctest.REPORT_NDIFF


def test_suite():
    suite = unittest.TestSuite()
    for doctest_file in get_doctest_files():
        suite.addTests([
            ztc.ZopeDocFileSuite(
                doctest_file,
                test_class=SimpleTestCase,
                optionflags=flags
            )
        ])
    return suite


def get_doctest_files():
    """Returns a list with the doctest files
    """
    files = resource_listdir(PRODUCT_NAME, "tests/doctests")
    files = filter(lambda file_name: file_name.endswith(".rst"), files)
    return map(lambda file_name: join("doctests", file_name), files)
