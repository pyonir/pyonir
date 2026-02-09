from pyonir import Pyonir, PyonirRequest

# Instantiate pyonir application
demo_app = Pyonir(__file__, use_themes=True)

def homepage(req: PyonirRequest):
    request = req.server_request
    if 'count' not in request.session:
        request.session['count'] = 1
    else:
        request.session['count'] = int(request.session['count']) + 1
    print("SESSION:", request.session)
    print("COOKIE HEADER:", request.headers.get("cookie"))
    username = "John Doe"
    count = request.session['count']
    return f'Hello, {username}: {count}!<a href="/hii">count</a></br><p>SESSION: {request.session}</p>'

routes = [
    ('/', homepage, ['GET']),
    ('/{path:path}', homepage, ['GET']),
]
demo_app.connected_clients = None
demo_app.load_routes(routes)
# Generate static website
# demo_app.generate_static_website()

# Run server
demo_app.run()
