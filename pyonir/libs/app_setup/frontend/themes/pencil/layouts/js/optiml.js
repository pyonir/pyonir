let SCOPE = [], DPK = [], CURS = null;
function skipUpdate(iml){
    // avoid updating iml nodes that are not in the current update keys
    if(!DPK.length) return false;
    return iml._dp && !(DPK && iml._dp && DPK.map(x=>iml._dp.includes(x)).filter(x=>x).length);
}
/*
* Listens for any user event from the application and delegates the actions
* */
function evtDelegator(root) {
    if (!root._gevts) return;
    const handler = (e) => {
        if (!e.target._evts) return;
        const elem = e.target;
        const {_ctx, _dp, _scope, _evts} = elem,
            fnNme = _evts[`_${e.type}`],
            evtFn = _scope.actions[fnNme] || getValue(fnNme.split("."), _ctx||_scope);
        if (evtFn) {
            _ctx ? evtFn(e, _ctx, _scope.state) : evtFn(e, _scope.state);
        }
        CURS = _ctx && _ctx.i;
        DPK = _dp || DPK;
        _scope._update();
    };
    root._gevts.forEach((evtName) => {
        evtName = evtName.replace('on','')
        root.removeEventListener(evtName, handler);
        root.addEventListener(evtName, handler);
    });
    SCOPE = [] // clear scope for multiple app
}

/*
* Access value on src data from path array
* */
function getValue(path, src) {
    return (path&&src) && path.reduce((val, p) => val[p], src)
}
/*
* Iterates an array of dom nodes with specified processing functions
* */
function process(nodes, processFn){
    let res = [];
    for (let node of [...nodes]) {
        let itrScope = SCOPE.length>1 && SCOPE[SCOPE.length-1]
        res.push(processFn(node, itrScope));
    }
    return res.filter(x=>x);
}
function processAll(node){
    const itrs = process(node.querySelectorAll('[each]:not([each] [each])'), processItrs);
    const txt = process(node.querySelectorAll('iml[js]'), processTxt);
    const attrs = process(node.querySelectorAll('[attrs]'), processAttr)
        .reduce((nl, alst)=>{return alst ? nl.concat(...alst) : nl}, []);
    return [...itrs, ...txt, ...attrs].filter(x=>x)
}
function processAttr(node, itrScope){
    const normAttr = (atr) => {
        // Process user events and dynamic attributes
        // We assign event props to the owner elements and
        // assign reactive props to standard props
        let {name, value} = atr;
        const root = SCOPE[0];
        const args = !!itrScope._each ? itrScope._args : `{${root._props}}`;
        const index = itrScope && itrScope._imls.length-1;
        const _isEvt = name.startsWith('on'),
            _isIml = value.indexOf('{') > -1;
        if(!_isIml) return;

        value = value.trim().replace(/[{}]/g, '');
        const owner = atr.ownerElement;
        const atrObj = {_scope: root}
        if(_isEvt){
            owner.removeAttribute(name);
            root._gevts.add(name);
            atrObj._evts = {[`_${name.replace('on','')}`]: value}
            if(itrScope){
                const dKey = itrScope._each, argKey = itrScope._args[itrScope._args.length-1]
                atrObj._ctx = {[argKey]: root.state[dKey][index], i: index}
                atrObj._update = function (ctx) {
                    this._ctx = ctx;
                }
            }
        }else{
            atrObj._update = Function(`${args}`, 'return this.nodeValue = `${' + value + '}`;')
        }
        Object.assign(_isEvt? owner : atr, atrObj);
        !_isEvt && atr._update(root.state)
        return (_isEvt && itrScope) ? owner : !_isEvt && atr;
    }
    node.removeAttribute('attrs')
    return process(node.attributes, normAttr);
}
function processTxt(node, itrScope){
    const root = SCOPE[0];
    const args = !!itrScope._each ? `{${itrScope._args}}` : `{${root._props}}`;
    const index = itrScope && itrScope._index;
    let expr = node.getAttribute('js');
    let txt = document.createTextNode(node.textContent);
    const useHtml = node.getAttribute('html')!==null; //expr may return html string
    const renderExpr = useHtml ? `
    const nxt = \`\${${expr}}\`;
            const onodes = Array.isArray(this._html) ? this._html : null;
            let node = document.createElement('div');
            node.innerHTML = nxt;
            nodes = [...node.childNodes];
            nodes.forEach(n=>this._pn.insertBefore(n, onodes?onodes[0]:this))
            this._html = nodes;
            !onodes ? this.remove() : onodes.forEach(n=>n.remove())
    ` : 'return this.nodeValue = `${' + expr + '}`;';
    node.replaceWith(txt);
    txt._scope = root;
    if(useHtml) {
        txt._html = true;
        txt._pn = txt.parentNode;
    }
    if(index!==undefined){txt._index = index;}
    txt._update = Function(`${args}`, renderExpr);
    return txt;
}
function processItrs(node, itrScope){
    // preprocess
    const eachParams = node.getAttribute('each');
    let [fnargs, itrKeyIndex] = !!eachParams ? eachParams.split(' in ').map(s => s.trim()) : [null, null];
    let [itrKey, index] = itrKeyIndex ? itrKeyIndex.split(',').map(x => x.trim()) : [null, null];
    index = Number(index)
    const data = getValue(itrKey.split('.'), SCOPE[0].state)
    const isLast = data.length-1 === index;
    const _isroot = index === 0 && !itrScope;
    node.removeAttribute('each')
    const templ = node.cloneNode(true);
    const Itr = {
        _index: index,
        _node: node,
        _imls: [],
    }
    if(_isroot || index === 0){
        SCOPE.push({
            _isroot,
            _scope: SCOPE[0],
            _each: itrKey,
            _args: (itrScope&&itrScope._args||[]).concat(fnargs.split(',')),
            _imls:[Itr],
            _templ: templ,
            _pn: node.parentNode,
            _size: data.length,
            _pvt: node.previousSibling,
            _update: function (ctx) {
                const state = this._scope.state;
                const list = getValue(this._each.split('.'), state);
                const max = (list.length - (this._size || this._imls.length));
                const prepend = this._head && (list[0] !== this._head) || null,
                    isMod = this._size !== list.length, // adds new each item
                    isPat = this._size === list.length, // in place updates
                    isDel = this._imls.length && (list.length===0 || list.length < (this._size || 0)); // removes each item
                this._size = list.length;
                const isFK = DPK.indexOf(this._each)<0;
                let cursor = !isFK && CURS && CURS>-1? CURS : (max<0? max*-1 : max);

                if (isDel) {
                    for (let index = 0; index < cursor; index++) {
                        if(index>=cursor) break;
                        this._imls.pop()._node.remove()
                    }
                    if(!this._imls.length) this._head = null;
                }

                // reconcile changes
                if (!isDel && isMod) {
                    for (let index = 0; index < cursor; index++) {
                        this._create(prepend)
                    }
                }

                // update dom
                for (let i in this._imls) {
                    i = Number(i)
                    const iml = this._imls[i];
                    if (i === 0) this._head = list[i];
                    if(!isFK && this._isroot && !isDel && CURS && CURS!==i) continue;
                    let ictx = this._args.reduce((_ctx,k)=>{
                        let currItr = this._args.indexOf(k)>-1;
                        _ctx[k] = k==='i'? Number(i) : currItr ? list[i] : ctx[k]
                        return _ctx
                        },{i, outer: ctx && {index: ctx.i}})
                    for(let j = 0; j < iml._imls.length; j++){
                        const tml = iml._imls[j];
                        tml._update(ictx)
                    }
                }
            },
            _create: function (prepend) {
                SCOPE = [this._scope, this];
                const _node = this._templ.cloneNode(true);
                this._insertElem(_node, this, prepend)
                const newItr = {_index: Number(this._size),_node,_imls:null}
                this._imls.push(newItr); // always update imls prior to hydrating node
                newItr._imls = processAll(_node);
            },
            _insertElem(newNode, itrNode, isPrep) {
                let head = (itrNode._imls.length ? itrNode._imls[0] : itrNode._pvt);
                head = head._node || head;
                if(!isPrep && itrNode._isroot) return itrNode._pn.append(newNode);
                let tail = itrNode._imls.length ? itrNode._imls[itrNode._imls.length-1] : head;
                itrNode._pn.insertBefore(newNode, isPrep? head : tail.nextSibling);
            }
        })
    }else{
        // always update imls prior to hydrating node
        itrScope && itrScope._imls.push(Itr)
    }
    Itr._imls = [...processAll(node)];
    if(isLast){
        return SCOPE.pop()
    }
}

function updateAll(imls, ictx, state){
    imls = imls || this._imls;
    state = state || this.state || this.scope.state;
    for (let iml of imls) {
        if(skipUpdate(iml)) continue;
        !!ictx ? iml._update(ictx, state) : iml._update(state);
    }
    // reconcile component changes
    if(this.components){
        for (const comp of this.components) {
            Object.keys(comp.deriveProps)
                .map(k=>{
                let compKey = comp.deriveProps[k];
                let nxtValue = comp.scope.state[k];
                comp.state[compKey] = nxtValue;
            });
            comp.update()
        }
    }
}

/*
* Hydrates a given appNode
* */
function mountApp(appNode){
    SCOPE.push(appNode);
    appNode._gevts = new Set();
    appNode._props = Object.keys(appNode.state).filter(x=>!x.startsWith('@'));
    appNode._update = updateAll
    appNode._imls = processAll(appNode);
    evtDelegator(appNode)
}

/*
* Client side renders interactive application
* */
function useClient(appId, appComponent){
    if(appId){
        const appNode = document.getElementById(appId);
        Object.assign(appNode, appComponent);
        mountApp(appNode, appId);
    }else{
        [...document.querySelectorAll('[iml-app]')].forEach(n=>{
            appId = n.getAttribute('iml-app') || n.id
            n._id = appId;
            useClient(appId, window[appId]);
            // clean up global scope
            delete window[appId];
        })
    }
}

/*
* Server side renders interactive ESM application
* */
function useServer(appModule){
    // Initialize esm app on node server
}
// auto hydrate nodes
useClient();