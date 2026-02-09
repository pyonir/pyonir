title: Demo SSE
menu.group: primary
````html content
This page demonstrates the functionality of server side events using pycasso

<button type="button" class="sse-close" onclick="sse.close()">Close</button>
<button type="button" class="sse-open" onclick="sse.open()">Open</button>
<ul class="sse">
<li>client: <txt js="${sse.id}"></txt><br/><strong>data: <txt js="progress: ${sse.data.time}"></txt></strong></li>
</ul>

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
    init(options={}){
        const url = !this.id ? `${this.url}?event=PYONIR_SSE_DEMO` : `${this.url}?last_event_id=${this.id}&event=PYONIR_SSE_DEMO`;
        this.es = new EventSource(url, options);
        for (let name in this.evtHandlers) {
            this.subTo(name, this.evtHandlers[name])
        }
    }
    open(){
        const resume = this.id ? {headers: {"Last-Event-ID": this.id}} : {};
        this.init(resume)
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
    let data = JSON.parse(evt.data);
    sse.data = data;
    sse.id = evt.lastEventId;
    sse.updateTemplate();
});
</script>
````
