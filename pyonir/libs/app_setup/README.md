# Contents
This directory stores a variety of data types used by the application.

- pages ( files used to return HTML only web request when file based routing is enabled)
- api (API endpoint files used to resolve JSON only web request or call resolver methods )

# Routes
A python method that accepts a web request for a given url.
Routes can be written as python methods or configured as file based routing using the parsely file configuration.

Pyonir uses a file based routing system by default. This can be disabled from the main.py file as a configuration parameter
`use_file_based_routing: False`

A file based routing allows the application to process web request based on the directory structure within the
`contents/pages` or `contents/api` File based routes that require custom endpoints for path resolution can be configured from the `main.py` file.

# Resolvers
File based router endpoints that dynamically calls available resource functions.
This means while the application is running, web endpoints with resolvers can be configured to call functions without needing to restart.

resolver can be configured within an `api` file using `@resolvers` property.

# Plugins
Plugins are custom features that extends your applications functionality. Plugins can apply to parsely files
or apply as a sub-application.

Plugins directory will store the plugin source code and any related data.

**Pyonir ships with the following optional plugins:**

- Forms
- Navigation
- FileUploader
- Ecommerce