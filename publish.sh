# Clean previous builds
rm -rf dist/ build/

# Install tools
#pip install build twine

# Build package
python -m build

# Check build
twine check dist/*

# Test upload to TestPyPI (optional)
twine upload --repository-url https://test.pypi.org/legacy/ -u "$TWINE_USERNAME" -p "$TWINE_TEST_PASSWORD" dist/*