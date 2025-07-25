@resolvers:
    POST.call: fileuploader.resolvers.endpoints.upload_file
    DELETE.call: fileuploader.resolvers.endpoints.delete_file
===
Upload file resources into the App's uploads directory using the fileuploader plugin