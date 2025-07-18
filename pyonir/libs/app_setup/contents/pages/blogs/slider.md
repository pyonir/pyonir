title: UI Slider
===
<slider>
<label for="range">
<input type="range" value="0" title="range-slider" oninput="updateSlider(event)" style="--range-value: 0%;">
<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon">
    <circle cx="12" cy="12" r="4" stroke="#fff" fill="#fff"></circle>
    <path d="M12 3v1"></path>
    <path d="M12 20v1"></path>
    <path d="M3 12h1"></path>
    <path d="M20 12h1"></path>
    <path d="m18.364 5.636-.707.707"></path>
    <path d="m6.343 17.657-.707.707"></path>
    <path d="m5.636 5.636.707.707"></path>
    <path d="m17.657 17.657.707.707"></path>
</svg>
</label>
</slider>
<script>
function updateSlider({target}){
    const value = target.value;
    target.style.setProperty('--range-value', `${value}`);
}
</script>
<style>
/* Example of basic styling */
label[for="range"]{
    position: relative;
}
label[for="range"] svg {
    position: absolute;
    top: 0px;
    left: 0;
    z-index: 9;
    margin: .61rem;
}
input[type="range"] {
    -webkit-appearance: none;
    width: 100%;
    height: 60px;
    background: linear-gradient(to right, #ccc 0%, #eee 100%);
    border-radius: 15px;
    outline: none;
    overflow: hidden;
    position: relative;
    display: block;
}
input[type="range"]::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 30px;
    height: 30px;
cursor: pointer;
}
input[type="range"]:before{
    content: '';
    display: block;
    width: calc(var(--range-value) * 1%);
    /*transform: calc(var(--range-value) * 1%);*/
    height: 100%;
    background: #000000;
    position: absolute;
}
</style>