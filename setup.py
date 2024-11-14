from setuptools import setup, find_packages

setup(
    name='pyonir',
    description='a python library for building web applications',
    url='https://pyonir.dev',
    author='Derry Spann',
    author_email='pyonir@derryspann.com',
    version='0.0.1',
    packages=find_packages(),
    entry_points={
        "console_scripts": ["pyonir-start = pyonir:cli.PyonirSetup"]
    }
)
