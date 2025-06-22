@resolvers:
    GET.call: pyonir.pyonir_sse_handler
    GET.headers.accept: text/event-stream
===
Sever sent event demo uses Pyonir's built in sse handler.