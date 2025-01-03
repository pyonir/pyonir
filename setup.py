from setuptools import setup, find_packages

with open("README.md", "r") as f:
    description = f.read()

setup(
    name='pyonir',
    description='a python library for building web applications',
    long_description=description,
    long_description_type="text/markdown",
    url='https://pyonir.dev',
    author='Derry Spann',
    author_email='pyonir@derryspann.com',
    version='0.0.4',
    packages=find_packages(),
    package_data={
        'pyonir': ['libs/*']
    },
    install_requires=['starlette==0.39.2', 'inquirer==3.4.0'],
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "pyonir-create = pyonir:cli.PyonirSetup"
        ]
    },
    python_requires=">=3.9"
)
