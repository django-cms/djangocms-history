from setuptools import find_packages, setup

import djangocms_undo


setup(
    name='djangocms-undo',
    packages=find_packages(),
    version=djangocms_undo.__version__,
    description=djangocms_undo.__doc__,
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
    url='http://github.com/divio/djangocms-undo',
    license='BSD',
)
