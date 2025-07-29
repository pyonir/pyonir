import pyonir
from backend import router
from plugins.pyonir_forms import Forms
# Instantiate pyonir application
demo_app = pyonir.init(__file__)

# Install plugins from pyonir registry repo based on plugin identifier
# demo_app.install_plugins(['ADD_PYONIR_PLUGIN_IDENTIFIER'])
# Install custom plugins from local app
demo_app.load_plugin([Forms])

# Generate static website
# demo_app.generate_static_website()

# Run server
demo_app.run(routes=router)
