from pyonir.parser import Parsely
from pyonir.types import IPlugin, IApp, os
from pyonir.utilities import dict_to_class

INPUT_ATTRIBUTES = tuple("accept,accept-charset,accesskey,action,align,allow,alt,async,autocapitalize,autocomplete,autofocus,autoplay,\
page.file_namebackground,bgcolor,border,buffered,capture,challenge,charset,checked,cite,class,code,codebase,color,cols,colspan,content,\
contenteditable,contextmenu,controls,coords,crossorigin,csp,data,data-*,datetime,decoding,default,defer,dir,dirname,disabled,\
download,draggable,dropzone,enctype,enterkeyhint,for,form,formaction,formenctype,formmethod,formnovalidate,formtarget,headers,\
height,hidden,high,href,hreflang,http-equiv,icon,id,importance,integrity,intrinsicsize,inputmode,ismap,itemprop,keytype,kind,\
label,lang,language,loading,list,loop,low,manifest,max,maxlength,minlength,media,min,multiple,muted,name,novalidate,open,optimum,\
pattern,ping,placeholder,poster,preload,radiogroup,readonly,referrerpolicy,rel,required,reversed,rows,rowspan,sandbox,scope,scoped,\
selected,shape,size,sizes,slot,span,\
spellcheck,src,srcdoc,srclang,srcset,start,step,style,summary,tabindex,target,title,translate,type,usemap,width,wrap".split(
    ','))


class InputTypes:
    SUBMIT = 'button'
    FIELDSET = 'fieldset'
    HTML = 'html'
    MULTISELECT = 'select-multiple'
    SELECT = 'select'
    SELECTONE = 'select'
    OPTION = 'option'
    EMAIL = 'email'
    TEXT = 'text'
    URL = 'url'
    COLOR = 'color'
    TEL = 'tel'
    PASSWORD = 'password'
    DATE = 'date'
    RADIO = 'radio'
    FILE = 'file'
    CHECKBOX = 'checkbox'
    TEXTAREA = 'textarea'
    HIDDEN = 'hidden'
    NUMBER = 'number'
    SECTION = 'section'


class ProductPrice:

    @property
    def lowest(self):
        return min(self.prices) if self.prices else None

    @staticmethod
    def process(value, base_price):
        if not value: return None

        def isInt(s):
            if isinstance(s, str):
                s = s.strip().replace('+', '')
            try:
                return "{:.2f}".format(float(s))
            except:
                return False

        price_value = isInt(value)
        upprice = None
        if price_value:
            try:
                price_value = float(price_value)
                upprice = True if isinstance(value, str) and '+' in value else False
            except:
                raise
        return price_value if not upprice else base_price + price_value

    def __init__(self, form) -> None:
        self.base_price = float(form.data.get('price', 0))
        self.prices = []
        try:
            for x in form.inputs:
                if not getattr(x, 'price_options') or not x.inputs: continue
                for y in x.inputs:
                    pr = self.process(y.props.get('value'), self.base_price)
                    if pr: self.prices.append(pr)
        except Exception as e:
            print("Form:ProductPrice parsing error found:", str(e))
            if self.base_price: self.prices = [self.base_price]
        pass


class Form(Parsely):
    parsely_extension = "form"

    @property
    def id(self):
        return self.data['form'].get('id')

    @property
    def method(self):
        return self.data['form'].get('method', 'GET')

    @property
    def action(self):
        return self.data['form'].get('action') or f"/api/v1/forms/{self.file_name}"

    @property
    def name(self):
        return self.data['form'].get('title', self.file_name)

    @property
    def type(self):
        return self.data['form'].get('type') or 'pyonir_form'

    @property
    def redirect(self):
        return self.data['form'].get('redirect')

    @property
    def js(self):
        return self.data['form'].get('js')

    @property
    def inputs(self):
        inputs = self.data['form'].get('inputs', [])
        return [FormCtrl(x, self) for x in inputs] if inputs else None

    def __init__(self, filepath: str, app_ctx: list):
        super().__init__(abspth=filepath, app_ctx=app_ctx)
        if self.type == 'product':
            self.price = ProductPrice(self)
            self.currency = "USD"


class FormCtrl:

    @property
    def price_options(self):
        """Indentifies if ctrl option has price options for product forms"""
        is_form = getattr(self.ctrl_parent, 'is_form')
        is_price_option = (not is_form and getattr(self.ctrl_parent, 'price_options')) or self._ctrl_data.get(
            'price_options', None)
        return True if is_price_option else False

    @property
    def price_increase(self):
        pval = self.props.get('value')
        return pval.startswith('+') if isinstance(pval, str) else None

    @property
    def label(self):
        return (self._ctrl_data.get('label') or '').replace('*', '')

    @property
    def required(self):
        return (self._ctrl_data.get('label') or '').startswith('*')

    @property
    def show_label(self):
        return self._ctrl_data.get('show_label') or True

    @property
    def selected(self):
        return self._ctrl_data.get('selected')

    @property
    def row_class(self):
        return self._ctrl_data.get('row_class')

    @property
    def html(self):
        return self._ctrl_data.get('html')

    @property
    def type(self):
        return self._ctrl_data.get('type') or InputTypes.HIDDEN

    @property
    def props(self):
        props = self._ctrl_data.get('props') or {}
        for prop in ['id', 'name', 'type', 'value', 'disabled', 'class']:
            v = self._ctrl_data.get(prop)
            props[prop] = v
            if prop == 'name' and not v:
                name = self.label.lower().replace(' ', '_')
                change_label = not name.startswith('item.attr')
                if self.ctrl_parent.type == 'product' and change_label:
                    name = 'item.attr.' + name
                props[prop] = name
        # self.props = props
        return props

    @property
    def inputs(self):
        if not self._ctrl_data.get('inputs'): return None
        return [FormCtrl(cinput, self) for cinput in self._ctrl_data.get('inputs')]

    def get_label_for(self):
        try:
            nm = self.ctrl_parent.label_for
            label_for = f"{nm}_{self.label}".lower().replace(' ', '_')
            return label_for
        except Exception as e:
            return str(e)

    def __init__(self, ctrl_data: dict, ctrl_parent=None):
        # assert isinstance(ctrl_data, dict), f"Expected a Dict but got a string value {ctrl_data} "
        # Normalize scalar ctrl options into dictionary types
        par_type = ctrl_parent and getattr(ctrl_parent, 'type', 'texty')
        child_type = 'option' if par_type == 'select' else par_type
        cpl = getattr(ctrl_parent, 'label_for', '')
        self._ctrl_data = ctrl_data if isinstance(ctrl_data, dict) else {"label": ctrl_data, "value": ctrl_data,
                                                                         "type": child_type}
        if not self._ctrl_data.get('label') and self.type != 'html':
            try:
                k, v = list(self._ctrl_data.items())[0]
                self._ctrl_data = {"label": k, "value": v, "type": child_type}
            except Exception as e:
                print(__name__, str(e))
        self.ctrl_parent = dict_to_class({
            "is_form": isinstance(ctrl_parent, Form),
            "label_for": cpl,
            "type": getattr(ctrl_parent, "type", None),
            "price_options": getattr(ctrl_parent, "price_options", None)
        }, 'CtrlParent')

        self.label_for = self.get_label_for()


class Forms(IPlugin):
    name = "Forms plugin"

    def __init__(self, app: IApp):
        self.forms = self.collect_dir_files(os.path.join(app.contents_dirpath, 'forms'),
                               app_ctx=app.files_ctx, file_type=Form)
        self.form_templates_dirpath = {os.path.join(os.path.dirname(__file__), 'templates')}
        self.register_templates(self.form_templates_dirpath, app)
        pass

    async def on_request(self, pyonir_req, app: IApp):
        parsely_file = pyonir_req.file
        if not isinstance(parsely_file.form, str): return
        f = getattr(self.forms, parsely_file.form)
        f.apply_filters()
        parsely_file.data['form'] = f
        pass