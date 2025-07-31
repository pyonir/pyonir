import pyonir
from backend import router
# Instantiate pyonir application
demo_app = pyonir.init(__file__)


# Install custom plugins from local app
# demo_app.load_plugin(['YOUR_PLUGIN_CLASS'])

# Generate static website
# demo_app.generate_static_website()

# Run server
demo_app.run(routes=router)
