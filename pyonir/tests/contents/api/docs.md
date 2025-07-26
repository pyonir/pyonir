title: Docs for app routing and services
@resolvers:
    GET.call: pyonir.server.pyonir_docs_handler
===
This endpoint retrieves a comprehensive list of available routes within the application, 
including details such as the route names, paths, and associated metadata (e.g., permissions, methods, etc.). 

It is typically used for purposes such as dynamically populating navigation menus, validating route access based on user permissions, or providing route data for analytics and routing-related tasks. 
The response is a JSON array, with each object representing a route and its relevant attributes. 
