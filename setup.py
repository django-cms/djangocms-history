from setuptools import find_packages, setup

import djangocms_history


INSTALL_REQUIREMENTS = [
    'Django>=1.8,<1.11',
    'django-cms>=3.4.2',
    'django-sekizai>=0.7',
]


setup(
    name='djangocms-history',
    packages=find_packages(),
    include_package_data=True,
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
    install_requires=INSTALL_REQUIREMENTS,
    author='Divio AG',
    author_email='info@divio.ch',
    url='http://github.com/divio/djangocms-history',
    license='BSD',
)
