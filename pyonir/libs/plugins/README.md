# Pyonir Plugins

Browse the collection of open source [pyonir plugins on github](https://github.com/pyonir/pyonir-plugins).

## Installation

**create a plugin directory within the pyonir project folder.**
```markdown
your_project/
    └─ plugins/
```

**git clone the plugin of choice into this directory**

```git clone <pyonir-plugin-repo> .```

**Register plugin to your pyonir app by importing the plugin class into `main.py`**

```python
# main.py
import pyonir
from plugins.some_plugin_package import SomePluginClass

# Instantiate pyonir application
demo_app = pyonir.init(__file__)

# Install plugins
demo_app.install_plugin(SomePluginClass)
```

## Configurations
Add `enabled_plugins` property to your `/contents/configs/app.md` file

```yml
# app.md
enabled_plugins:- <YOUR_PLUGIN_DIRECTORY_NAME>
```