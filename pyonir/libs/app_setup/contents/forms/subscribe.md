form.title: Subscriber Demo
form.id: art_lovers_form
form.subtitle: Join our list of Python Lovers?
form.action: /api/demo-form-handler
form.method: POST
form.auth.user: False
form.button: Send Email
form.schema: EmailSubscriber
form.inputs:-
    label: *Email
    type: email
    placeholder: PabloPycasso@pyonir.dev
    -
    label: Subscriptions
    type: checkbox
    inputs:-
        Beyonce
        Masego
        WuTang
    -
    label: Sign In
    type: submit
    class: btn
===form.message
Thank you for subscribing to {subscriptions}!
===form.js
<script defer>
art_lovers_form.addEventListener('change', (e)=>{
    console.log(e.target)
})
</script>
