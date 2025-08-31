inline_list_of_scalrs_types:- 1, true, hello, 3.14
single_item_list:- just one thing here
string_phonenumber: (111) 123-3456
string_types: 1, true, hello, 3.14
# single line comment
basic: scalar value
dict_value:
    my_key: my_value
    another_key: another_value
list_value:-
    one
    two
    three
# list of scalars with one map
dynamic_list_blocks:-
    ages:-
        1
        true
        hello
        3.14
        dict_key: dict_value
    -
    this:
        age: 3
        key: some value
inline_list_of_scalrs_types:- 1, true, hello, 3.14
inline_list_of_maps:- one: 1, two: true, three: hello
inline_dict_value: my_lnkey: my_lnvalue, another_lnkey: another_lnvalue
$ReferenceData:
    name: hal
    city:
        name: halfax
        zip: 21343
multiline_block:|
What is this here? Content types enable you to organize and manage content in a consistent way for specific kinds of pages.
there is no such thing as a Python JSON object. JSON is a language independent file 
format that finds its roots in JavaScript, and is supported by many languages. end of mulitiline block.
````js
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function() {
    navigator.serviceWorker.register('/public/pwa/js/service-worker.js');
  });
}
````
content:|
What is this here? Content types enable you to organize and manage content in a consistent way for specific kinds of pages.
there is no such thing as a Python JSON object. JSON is a language independent file 
format that finds its roots in JavaScript, and is supported by many languages. If your YAML
````html
<app-screen>
    <footer>
        <span subtitle>Hello</span>
        <img src="/public/some-image.jpg" alt="find dibs logo">
        <button type="submit">Join Pyonir</button>
    </footer>
</app-screen>
````