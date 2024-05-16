from setuptools import setup
import isg_scripts


setup(name='isg_scripts',
    version=isg_scripts.__version__,
    description='Library to analyse CAN data for isg applications',
    long_description='',
    url='http://www.sedemac.com',
    author='RnD Sedemac',
    author_email='',
    license='SEDEMAC',
    packages=['isg_scripts',
              'isg_scripts.deadtrace',
              'isg_scripts.firetrace',
              'isg_scripts.speedtime',
    ],
    install_requires=[
        'scipy',
        'numpy',
        'pandas',
        'click',
        'matplotlib',
    ],
    scripts=[
    ],
    entry_points={
        'console_scripts': {
            'isg.deadtrace= isg_scripts.deadtrace.deadtrace:cli',
            'isg.firetrace= isg_scripts.firetrace.firetrace:cli',
            'isg.assist= isg_scripts.assist:cli',
            'isg.speedtime= isg_scripts.speedtime.speedtime:cli',
        }
    },
    include_package_data=True,
    zip_safe=False)
