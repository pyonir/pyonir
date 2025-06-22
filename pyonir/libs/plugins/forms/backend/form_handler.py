from pyonir.types import PyonirRequest


async def form_handler(request: PyonirRequest):
    """General form handler"""
    # print('New Form submission', request.form)
    request.server_request.session[request.form.get('form_id','__forms__')] = request.form
    return request.form