@resolvers:
    GET.call: backend.sse_handler
    GET.headers.accept: text/event-stream
===
Sever sent event demo uses Pyonir's built in sse handler.