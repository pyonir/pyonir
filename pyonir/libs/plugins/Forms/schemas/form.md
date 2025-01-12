$Props:
    id: string
    name: string
    type: string
    value: string
    disabled: string
    class: string
    @safe: true
$InputCtrl:
    html: string
    inputs:- ?$InputCtrl
    label: string
    label_for: string
    price_increase: bool
    price_options: bool
    props: $Props
    required: bool
    row_class: string
    selected: bool
    show_label: bool
    type: string
$Price:
    base_price: float
    lowest: float
    prices:- float
action: string
js: string
method: string
redirect: string
type: string
inputs:- $InputCtrl
price: $Price
@fk:- inputs
@pk: file_path
