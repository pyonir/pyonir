from pyonir import Pyonir

# Instantiate pyonir application
demo_app = Pyonir(__file__)

# Install plugins
# demo_app.install_plugin(ADD_PLUGIN_CLASS_HERE)

# Generate static website
# demo_app.generate_static_website()

# Run server
demo_app.run()
