from setuptools import setup

# get version
__version__ = None
exec(open('pytest_alvin/version.py').read())

setup(
    name='pytest-alvin',
    version=__version__,
    description="Alvin pytest fixtures",
    packages=[
        'pytest_alvin',
    ],
    package_data={},
    entry_points={
        'pytest11': [
            'alvin = pytest_alvin.plugin',
        ],
    },
    scripts=[],
    install_requires=[
        'freezegun>=0.3'
    ],
)
