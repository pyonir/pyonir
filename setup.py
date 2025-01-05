from setuptools import setup, find_packages

with open("README.md", "r") as f:
    description = f.read()

setup(
    name='pyonir',
    description='a python library for building web applications',
    long_description=description,
    long_description_content_type="text/markdown",
    url='https://pyonir.dev',
    author='Derry Spann',
    author_email='pyonir@derryspann.com',
    version='0.0.6',
    packages=find_packages(),
    package_data={
        'pyonir': ['libs/*']
    },
    install_requires=['starlette', 'inquirer', 'uvicorn', 'starlette_session', 'starlette_wtf', 'pytz',
                      'sortedcontainers', 'jinja2', 'webassets'],
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "pyonir-create = pyonir:cli.PyonirSetup"
        ]
    },
    python_requires=">=3.9"
)
