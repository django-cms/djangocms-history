# -*- coding: utf-8 -*-
from distutils.version import LooseVersion

from cms import __version__

# Django >= 3.6
CMS_GTE_36 = LooseVersion(__version__) >= LooseVersion('3.6')
