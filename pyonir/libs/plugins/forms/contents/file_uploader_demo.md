form.title:File Uploader Plugin
form.type: media
form.action:/api/demo-uploads
form.method:POST
form.inputs:-
    label: Gallery Folder
    type: text
    placeholder: type gallery name
    data-parent: files
    name: foldername
    id: foldername
    -
    label: Attach Image
    type: file
    id: file
    -
    label: Upload
    type: submit
===form.message
your {count} files were uploaded! {uploads}
