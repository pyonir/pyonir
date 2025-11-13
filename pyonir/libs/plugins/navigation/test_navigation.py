from pyonir import Pyonir
from pyonir.libs.plugins.navigation import Navigation

app = Pyonir(__file__)
app.CONTENTS_DIRNAME = ""
app.PAGES_DIRNAME = "tests"
nav_plugin = Navigation(app)

def test_navigation_menus_loaded():
    assert isinstance(nav_plugin.menus, dict)
    assert nav_plugin.menus  # Should not be empty if menus are loaded

def test_navigation_menu_get():
    menu = nav_plugin.menus.get("navigation")
    assert menu is not None
pass