title: Demo SSE
===
This page demonstrates the functionality of server side events using pycasso

<button type="button" class="sse-close" onclick="sse.close()">Close</button>
<button type="button" class="sse-open" onclick="sse.open()">Open</button>
<ul class="sse">
<li>client: <txt js="${sse.id}"></txt><br/><strong>data: <txt js="progress: ${sse.data.time}"></txt></strong></li>
</ul>
=== js
<script>
class SSEManager {
    constructor(sse_url){
        this.id = undefined;
        this.es = null;
        this.url = sse_url;
        this.evtHandlers = {};
        this.data = {};
        this.refs = [...document.querySelectorAll('txt')].map(t=>{
            let jsexpr = t.getAttribute('js');
            let update = Function('sse', `return this.textContent = \`${jsexpr}\``);
            const txt = document.createTextNode('...');
            txt.update = update;
            t.replaceWith(txt);
            return txt;
        });
        this.init();
    }
    updateTemplate(){
        for(let ref of this.refs){
            ref.update(this);
        }
    }
    init(){
        const url = !this.id ? `${this.url}?event=PYONIR_SSE_DEMO` : `${this.url}?id=${this.id}&event=PYONIR_SSE_DEMO`;
        this.es = new EventSource(url);
        for (let name in this.evtHandlers) {
            this.subTo(name, this.evtHandlers[name])
        }
    }
    open(){
        this.init()
    }
    close(){
        this.es.close();
    }
    subTo(sseEvtName, evtHandler){
        this.evtHandlers[sseEvtName] = evtHandler;
        if(!this.es) return;
        this.es.removeEventListener(sseEvtName, evtHandler);
        this.es.addEventListener(sseEvtName, evtHandler);
    }
}
const sse = new SSEManager("/api/demo-sse-resolver");
sse.subTo("PYONIR_SSE_DEMO", (evt)=>{
    if(!sse.id) sse.id = evt.lastEventId;
    let data = JSON.parse(evt.data);
    sse.data = data;
    sse.updateTemplate();
});
</script>