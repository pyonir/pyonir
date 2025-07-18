@filter.md:- content
title: UI stepper
===
Default orientation is horizontal `stepper`.

<nav class="stepper">
<button type="button"><span>1</span></button>
<button type="button"><span>2</span></button>
<button type="button"><span>3</span></button>
</nav>

<stepper>
<dot type="button"><span>1</span></dot>
<dot type="button"><span>2</span></dot>
<dot type="button"><span>3</span></dot>
</stepper>

Vertical orientation with `vertical` class attribute.

<nav class="stepper vertical">
<button type="button"><span>1</span></button>
<button type="button"><span>2</span></button>
<button type="button"><span>3</span></button>
</nav>
<style>
:root{
    --dot-size: 23px;
    --line-color: #171717;
    --dot-color: #181818;
    --dot-border-color: transparent;
}
.stepper.vertical{
    flex-direction: column;
    width: 20px;
    height: 100%;
}
.stepper.vertical:before{
    top: 0;
    width: 1px;
    left: 55%;
    height: 100%;
    background: var(--line-color);
}
.stepper, stepper {
    position: relative;
    display: flex;
    width: auto;
    justify-content: space-between;
}
.stepper:before, stepper:before{
    content: "";
    position: absolute;
    top: 50%;
    width: 100%;
    left: 0;
    height: 1px;
    background: var(--line-color);
}
.stepper button, stepper dot {
    height: var(--dot-size);
    width: var(--dot-size);
    border-color: var(--dot-border-color);
    background: var(--dot-color);
    border-radius: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    /* transform: scale(0.5); */
    transition: transform 0.3s ease-in-out;
    cursor: pointer;
    color: white;
}
</style>
