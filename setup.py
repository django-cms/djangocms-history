from setuptools import find_packages, setup

import djangocms_history


setup(
    name='djangocms-history',
    packages=find_packages(),
    version=djangocms_history.__version__,
    description=djangocms_history.__doc__,
    long_description=open('README.rst').read(),
    classifiers=[
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Topic :: Software Development'
    ],
    author='Divio AG',
    author_email='info@divio.ch',
    url='http://github.com/divio/djangocms-history',
    license='BSD',
)
