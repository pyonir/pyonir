# this package is now discoverable by the app setup backend
import json, time
from typing import AsyncGenerator
from starlette.websockets import WebSocket, WebSocketState

from pyonir import PyonirRequest



def generate_id():
    import uuid
    return uuid.uuid4().hex

def get_client_ua(request):
    ua = request.headers.get("user-agent", "").lower()

    if "edg/" in ua:
        return "edge"
    if "chrome/" in ua and "edg/" not in ua:
        return "chrome"
    if "firefox/" in ua:
        return "firefox"
    if "safari/" in ua and "chrome/" not in ua:
        return "safari"

    return "unknown"

def process_sse(data: dict) -> str:
    """Formats a string and an event name in order to follow the event stream convention.
    'event: Jackson 5\\ndata: {"abc": 123}\\n\\n'
    """
    import json
    sse_payload = ""
    for key, val in data.items():
        val = json.dumps(val) if key == 'data' else val
        sse_payload += f"{key}: {val}\n"
    return sse_payload + "\n"

async def sse_handler(request: PyonirRequest) -> AsyncGenerator:
    """Handles Server-Sent Events (SSE) connections, allowing clients to receive real-time updates from the server."""
    import asyncio
    from pyonir.core.utils import get_attr
    from pyonir.core.server import EVENT_RES
    request.server_response.set_media(EVENT_RES)  # assign the appropriate streaming headers
    ConnClients = {} if request.pyonir_app.connected_clients is None else request.pyonir_app.connected_clients
    # set sse client
    event = get_attr(request.query_params, 'event')
    retry = get_attr(request.query_params, 'retry') or 1000
    close_id = get_attr(request.query_params, 'close')
    interval = 1  # time between events
    ua = get_client_ua(request)
    last_event_id = request.headers.get("last-event-id", request.request_input.body.get("last_event_id"))
    client_id = last_event_id or f"{ua}_{generate_id()}"

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
        request.pyonir_app.connected_clients = ConnClients

    while True:
        if await request.server_request.is_disconnected():
            print("Client disconnected")
            break
        last_client["data"]["time"] = last_client["data"]["time"] + 1
        res = process_sse(last_client)
        await asyncio.sleep(interval)  # Wait for 5 seconds before sending the next message
        yield res
    print(f"Client {client_id} disconnected")

async def pyonir_ws_handler(websocket: WebSocket, request: PyonirRequest):
    """ws connection handler"""

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

    ConnClients = {} if request.pyonir_app.connected_clients is None else request.pyonir_app.connected_clients
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
