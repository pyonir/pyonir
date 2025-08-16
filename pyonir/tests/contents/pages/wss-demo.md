@filter.md:- content
@filter.jinja:- js
title: Websockets Chat demo
===
This page demonstrates the functionality of websockets using pycasso library.
Visit this page in another browser to test functionality.

<style>
#inbox article {
    border-radius: 20px;
    padding: 1rem 2rem;
    background: greenyellow;
    margin-bottom: 1rem;
    &.client-msg {
    
        text-align: right;
        background: aliceblue;
    }
}
</style>
<div style="display:block;">
<dl>
    <dt>Your Chat ID:</dt>
    <dd id="chatid"></dd>
</dl>
<ul id='outbox'>
<form action="" onsubmit="sendMessage(event)">
    <input type="text" id="messageText" autocomplete="off"/>
    <button>Send</button>
</form>
</ul>
<ul id='inbox'></ul> 

</div>

=== js
<script>
    var domain = location.host;
    var protocol = location.protocol==='https:'?'wss':'ws';
    function chatBubble([txt, time, isclient]){
        return `
        <article id="chat-msg" ${isclient?'class="client-msg"':''}>
            <div class="icon">
                <img src="/public/favicon.ico" alt="chat demo">
            </div>
            <div class="msg">
                <p ${isclient?'class="text-white"':''}>${EmojiPics(txt)}</p>
                <span style=" font-size: 11px; display: block; color: gray; ">${Date(time)}</span>
            </div>
        </article>`
    }
    function EmojiPics(txt){
        let is_image = txt.endsWith('.jpg') || txt.endsWith('.gif');
        if( is_image ){
            return `<img src="${txt}" width="60px"/>`
        }
        return txt;
    }
    function ChatMsg([txt, time, isclient], trgt){
        const color = isclient ? `green` : 'blue';
        const tmpl = chatBubble([txt, time, isclient]);
        trgt.insertAdjacentHTML('afterbegin', tmpl)
    }
    const chatState = {
        wsReady: null,
        id: null,
        inbox: [],
        outbox: []
    }
    var ws = new WebSocket(`${protocol}://${domain}/sysws`);
    ws.onopen = function(e){
        chatState.wsReady = true;
        console.log('open', e.data)
    };
    ws.onerror = function(e){
        console.log(e)
    };
    ws.onclose = function(e){
        console.log('close', e)
    };
    ws.onmessage = function(event) {
        var payload = JSON.parse(event.data);
        var action = payload.action;
        switch(action){
            case 'ON_CONNECTED':
                chatState.id = payload.id;
                chatid.textContent = payload.id;
                break;
            case 'DISCONNECT_PLAYER':
                break;
            default:
                break;
        }
        if (action){ 
            console.log(payload);
            return 
        }
        chatState.inbox.push([payload.value, Date.now()]);
        ChatMsg([payload.value, Date.now(), 1], inbox);
        console.log('inbox..',payload)
    };
    function sendMessage(event) {
        var input = document.getElementById("messageText");
        chatState.outbox.push([input.value, Date.now()]);
        ChatMsg([input.value, Date.now()], inbox);
        ws.send(JSON.stringify({"value":input.value}));
        input.value = '';
        event.preventDefault()
    }
</script>
