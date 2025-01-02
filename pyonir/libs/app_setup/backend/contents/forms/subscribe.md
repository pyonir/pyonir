form.title: Subscriber Demo
form.id: art_lovers_form
form.subtitle:Join our list of Art Lovers?
form.action:/api/forms
form.method:POST
form.auth.user: False
form.button: Send Email
form.inputs:-
    label: redirect_to
    type: hidden
    value: /thanks-for-joining
    -
    label: *Email
    type: email
    placeholder: PabloPycasso@pyonir.dev
    -
    label: Sign In
    type: submit
    class: btn
===form.js
<script defer>
art_lovers_form.addEventListener('change', (e)=>{
    console.log(e.target)
})
</script>