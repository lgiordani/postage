#!/usr/bin/env python
# -*- coding: utf-8 -*-

import test_postage

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(test_postage.suite())
