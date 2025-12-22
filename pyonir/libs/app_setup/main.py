from pyonir import Pyonir
# Instantiate pyonir application
demo_app = Pyonir(__file__)

# Generate static website
# demo_app.generate_static_website()

# Run server
demo_app.run()
