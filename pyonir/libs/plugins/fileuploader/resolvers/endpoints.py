from pyonir.types import PyonirRequest
from pyonir.parser import ParselyMedia
import os

async def delete_file(request: PyonirRequest):
    """Deletes a document"""
    from pyonir import Site
    import os
    docpath = os.path.join(Site.uploads_dirpath, getattr(request.query_params,'file_id'))
    doc: ParselyMedia = ParselyMedia.from_path(docpath, Site.app_ctx)
    if doc.file_exists:
        os.remove(doc.file_path)
        if doc.is_thumb:
            os.remove(os.path.join(doc.file_dirpath, doc.full_url))
        for _, timg in doc.thumbnails.items():
            os.remove(timg.file_path)
    return f"{doc.file_name} was deleted"

async def upload_file(request: PyonirRequest):
    """Uploads a document"""

    from pyonir import Site
    folder_name = request.form.get('foldername')
    uploads = []
    for doc in request.files:
        parselyMedia = await ParselyMedia.save_upload(doc, os.path.join(Site.uploads_dirpath, folder_name), Site.app_ctx)
        parselyMedia.resize()
        uploads.append(parselyMedia.to_json())
    request.server_request.session[request.form.get('form_id','__forms__')] = {"uploads": uploads, "count": len(uploads)}
    return uploads