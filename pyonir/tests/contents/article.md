@extends: $dir/pages/foo.md
$ReferenceData:
    name: hal
    city:
        name: halfax
        zip: 21343
title: A leading article headline
we.all.love: pyonir
single_item_list:- just one thing here
string_phonenumber: (111) 123-3456
string_types:- 1, true, hello, 3.14
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
# single line comment
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
inputs:-
    label: Caption
    type: textarea
    -
    label: Status
    html:|
        <div class="flex items-center gap-x-3">
          <label for="hs-basic-with-description" class="text-sm text-gray-500 dark:text-neutral-400">Off</label>
          <label for="hs-basic-with-description" class="relative inline-block w-11 h-6 cursor-pointer">
            <input type="checkbox" id="hs-basic-with-description" class="peer sr-only">
            <span class="absolute inset-0 bg-gray-200 rounded-full transition-colors duration-200 ease-in-out peer-checked:bg-blue-600 dark:bg-neutral-700 dark:peer-checked:bg-blue-500 peer-disabled:opacity-50 peer-disabled:pointer-events-none"></span>
            <span class="absolute top-1/2 start-0.5 -translate-y-1/2 size-5 bg-white rounded-full shadow-xs transition-transform duration-200 ease-in-out peer-checked:translate-x-full dark:bg-neutral-400 dark:peer-checked:bg-white"></span>
          </label>
          <label for="hs-basic-with-description" class="text-sm text-gray-500 dark:text-neutral-400">On</label>
        </div>
    -
    label: Category
    type: select
    inputs:- News, Updates, Tutorials
person: $ReferenceData
===
# hello new article post

we love pyonir. and we love:

- python
  - javascript
  - html
  - css