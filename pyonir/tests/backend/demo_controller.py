import json

from pyonir.core import PyonirRequest, PyonirApp
from pyonir.tests.backend.models.email_subscriber import EmailSubscriber
from starlette.websockets import WebSocketState, WebSocket
from typing import AsyncGenerator

ConnClients = {}

async def dynamic_lambda(request: PyonirRequest) -> str:
    return "hello battle rap forever!"

async def demo_items(request: PyonirRequest, sample_id: int=99, version_id: str='0.1'):
    """Home route handler"""
    return f"Main app ITEMS route {sample_id}! {version_id}"

async def subscriber_model(subscriber: EmailSubscriber):
    """Demo takes request body as parameter argument"""
    print(subscriber)
    return subscriber

async def subscriber_values(email: str, subscriptions: list[str]):
    """Demo takes request body as parameter arguments"""
    print(email, subscriptions)
    return f"subscribing {email} to {subscriptions}"

async def some_route(name: str = 'pyonir'):
    return f"hello router annotation {name}"

class DemoService:

    def __init__(self, app: PyonirApp):
        self.items = ['python','javascript']
        self.app = app

    @staticmethod
    def get_numbers(num: int):
        return 42, num or 88, 86

    def get_items(self):
        return self.items + ['purejs','optimljs']


# Demo routers

def pyonir_index(request: PyonirRequest):
    """Catch all routes for all web request"""
    pass

async def pyonir_ws_handler(websocket: WebSocket):
    """ws connection handler"""
    from pyonir.utilities import generate_id

    async def get_data(ws: WebSocket):
        assert ws.application_state == WebSocketState.CONNECTED and ws.client_state == WebSocketState.CONNECTED
        wsdata = await ws.receive()

        if wsdata.get('text'):
            wsdata = wsdata['text']
            swsdata = json.loads(wsdata)
            swsdata['value'] = swsdata.get('value')
            wsdata = json.dumps(swsdata)
        elif wsdata.get('bytes'):
            wsdata = wsdata['bytes'].decode('utf-8')

        return wsdata

    async def broadcast(message: str, ws_id: str = None):
        for id, ws in ConnClients.items():
            if active_id == id and hasattr(ws, 'send_text'): continue
            await ws.send_text(message)

    async def on_disconnect(websocket: WebSocket):
        del ConnClients[active_id]
        client_data.update({"action": "ON_DISCONNECTED", "id": active_id})
        await broadcast(json.dumps(client_data))

    async def on_connect(websocket: WebSocket):
        client_data.update({"action": "ON_CONNECTED", "id": active_id})
        await websocket.send_text(json.dumps(client_data))

    active_id = generate_id()
    client_data = {}
    await websocket.accept()  # Accept the WebSocket connection
    print("WebSocket connection established!")
    ConnClients[active_id] = websocket
    await on_connect(websocket)
    try:
        while websocket.client_state == WebSocketState.CONNECTED:
            # Wait for a message from the client
            data = await get_data(websocket)
            print(f"Received from client: {data}")
            # Respond to the client
            await broadcast(data)
        await on_disconnect(data)
    except Exception as e:
        del ConnClients[active_id]
        print(f"WebSocket connection closed: {active_id}")

def process_sse(data: dict) -> str:
    """Formats a string and an event name in order to follow the event stream convention.
    'event: Jackson 5\\ndata: {"abc": 123}\\n\\n'
    """
    sse_payload = ""
    for key, val in data.items():
        val = json.dumps(val) if key == 'data' else val
        sse_payload += f"{key}: {val}\n"
    return sse_payload + "\n"

async def pyonir_docs_handler(request: PyonirRequest):
    """Documentation for every endpoint by pyonir"""
    return {"routes": request.server_request.app.url_map, "configs": request.auth.app._env}


async def pyonir_sse_handler(request: PyonirRequest) -> AsyncGenerator:
    """Handles sse web request by pyonir"""
    import asyncio
    from pyonir.utilities import generate_id, get_attr
    from pyonir.models.server import EVENT_RES
    request.type = EVENT_RES  # assign the appropriate streaming headers
    # set sse client
    event = get_attr(request.query_params, 'event')
    retry = get_attr(request.query_params, 'retry') or 1000
    close_id = get_attr(request.query_params, 'close')
    interval = 1  # time between events
    client_id = get_attr(request.query_params, 'id') or request.headers.get('user-agent')
    client_id += f"{client_id}{generate_id()}"
    if close_id and ConnClients.get(close_id):
        del ConnClients[close_id]
        return
    last_client = ConnClients.get(client_id, {
        "retry": retry,
        "event": event,
        "id": client_id,
        "data": {
            "time": 0
        },
    })
    # register new client
    if not ConnClients.get(client_id):
        ConnClients[client_id] = last_client

    while True:
        last_client["data"]["time"] = last_client["data"]["time"] + 1
        is_disconnected = await request.server_request.is_disconnected()
        if is_disconnected or close_id:
            del ConnClients[client_id]
            break
        await asyncio.sleep(interval)  # Wait for 5 seconds before sending the next message
        res = process_sse(last_client)
        yield res

