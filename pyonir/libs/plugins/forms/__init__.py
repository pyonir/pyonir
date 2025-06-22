import dataclasses
from dataclasses import field
from pyonir.parser import Parsely

from pyonir.types import PyonirApp, os, PyonirRequest, PyonirPlugin

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


@dataclasses.dataclass
class CtrlForm:
    label: str
    type: str
    required: bool = False
    inputs: list["CtrlForm"] = field(default_factory=list)
    props: dict = field(default_factory=dict)
    label_for: str = ''

    def __post_init__(self):
        """Returns snake case format of label"""
        self.label_for = self.label.lower().replace(' ','_')

    @classmethod
    def from_dict(cls, file_data: dict):
        data = file_data
        # Only pass keys that match field names
        field_names = {f.name for f in dataclasses.fields(cls)}
        filtered_data = {"props": {}}
        input_type = data.get('type')
        for k, v in data.items():
            if k in field_names:
                if k == 'inputs' and isinstance(v, list):
                    v = [CtrlForm(label=cv, type=input_type) for cv in v] # convert scalar list into object list
                if k == 'label' and v.startswith('*'):
                    v = v[1:]
                    filtered_data['required'] = True
                filtered_data[k] = v
            else:
                filtered_data['props'][k] = v
        return cls(**filtered_data)


@dataclasses.dataclass
class Form:
    _mapper = {'file_path': 'abspath'}
    title: str
    action: str
    inputs: list[CtrlForm]
    id: str = ''
    type: str = ''
    redirect: str = ''
    method: str = 'GET'
    button: str = ''
    schema: str = ''
    js: str = ''
    message: str = ''
    subtitle: str = ''
    file_name: str = None
    file_path: str = ''

    def get_message(self, request: PyonirRequest):
        """Returns a formatted response message after form submission using the values submitted"""
        # pop and return the messages after form submission
        ctx = request.server_request.session.pop(self.file_name, None)
        try:
            return self.message.format(**ctx)
        except (KeyError, TypeError) as e:
            return f'no messages for {self.file_name}'


class Forms(PyonirPlugin):
    name = "Forms plugin"

    def __init__(self, app: PyonirApp):
        self.FRONTEND_DIRNAME = 'templates'
        super().__init__(app, __file__)
        # Preload application's forms content
        self.app_forms = self.query_files(os.path.join(app.contents_dirpath, 'forms'), app_ctx=app.app_ctx, model_type=Form)

        # Prepare demo form
        demo_form_path = os.path.join(os.path.dirname(__file__), 'contents', 'file_uploader_demo.md')
        demo_form = Parsely(demo_form_path, self.app_ctx).map_to_model(Form)
        setattr(self.app_forms, demo_form.file_name, demo_form)
        # self.forms = [demo_form]
        # for form in app_forms:
        #     self.forms.append(form)
        # Register Form plugin templates to be accessible from application
        self.register_templates([self.frontend_dirpath])
        self.resolvers_dirpath = os.path.join(os.path.dirname(__file__))
        pass

    async def on_request(self, pyonir_req, app: PyonirApp):
        parsely_file = pyonir_req.file
        form_name = parsely_file.data.get('form')
        if not isinstance(form_name, str): return
        f = getattr(self.app_forms, form_name, None) #next((f for f in self.forms if f.file_name == form_name), None)
        if not f: return
        parsely_file.data['form'] = f
        pass
