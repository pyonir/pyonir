### Configure Plugins
Plugins extend the core functionality of pyonir and add new features, modify existing behavior, or integrate with third-party services.

To install a plugin, use the pyonir CLI tool.

**Install plugins from the pyonir plugins registry on github**

```bash
> pyonir install plugin:<repo_owner>/<repo_name>#<repo_branch>
```

**Install themes from the pyonir theme registry on github**

```bash
> pyonir install theme:<repo_owner>/<repo_name>#<repo_branch>
```

### Introduction

Plugins contains code used during the pyonir runtime to perform operations, route request and host templates.

### Plugin content pages

When a request is made to a plugin-specific endpoint, any pages located in the @<plugin_name> directory will be used to handle that request.
Templates shipped with the plugin can be referenced using paths such as:

```yaml
template: @<plugin_name>/templates/some_page.html
```