import pyonir
# Instantiate pyonir application
demo_app = pyonir.init(__file__, use_themes=True)

# Generate static website
# demo_app.generate_static_website()

# Run server
demo_app.run()
