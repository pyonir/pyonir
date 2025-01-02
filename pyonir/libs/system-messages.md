=== 404
The requested url `{{request.path}}` was not found!
=== 401
The requested url `{{request.path}}` is Unauthorized!
=== WRONG_USER_GRP
Sorry you are in the <strong>{{usr.group}}</strong> group. You must be in the <strong>{{form.group}}</strong> group to perform that action!
=== ILLEGAL_ACTION
You are performing an illegal operation. A System administrator will be notified.
===AUTH_CREDS_FAILED 
We couldn't provide access to that account using those credentials.
===VALIDATION_ERROR
Form has an error.
===SYSTEM_ERROR
A System error has occured. code 11
===NO_SCHEMA
No schema definition was found for {{form_name}}
===GENERIC_FORM_SUBMISSION
Thank You for submitting to our {{form_name| replace('_',' ')|replace('-',' ') | title }}.
===API_NO_AUTH_TOKEN
Auth token has expired or wasn't provided.
=== USER_SESSION_EXPIRED
User session has expired.
=== NO_USER_SESSION
User session not found. You must be logged in to access this resource.
===USER_LOGIN_SUCCESS
Hi {{usr.first_name}}, you have signed in successfully.
===UPLOAD_SUCCESS
Successfully uploaded {{files}}