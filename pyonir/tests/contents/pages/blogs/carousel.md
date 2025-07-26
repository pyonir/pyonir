title: Carousel  
===
<slider id="slider">

<hero>
<header>
<h1>Main Title</h1>
<h2>Sub Title</h2>
</header>
<img decoding="async" src="https://i.pinimg.com/736x/b5/f1/fd/b5f1fdf458910488f3f62484f1a36dfe.jpg" class="current">
<img decoding="async" src="https://i.pinimg.com/1200x/da/24/46/da2446c91ec6fa6876acb36b2a396ea3.jpg" class="">
<img decoding="async" src="https://i.pinimg.com/736x/df/77/ff/df77ffc6cc4baf42f36e26b40a3e6237.jpg" class="">
<img decoding="async" src="https://i.pinimg.com/1200x/0d/9e/4d/0d9e4dab729f9711e6a685e163e36b39.jpg" class="">
</hero>

<slider-controls>
<slider-thumbnails>
<figure id="slide1">
    <img decoding="async" src="https://i.pinimg.com/1200x/da/24/46/da2446c91ec6fa6876acb36b2a396ea3.jpg" class="">
  <figcaption>An elephant at sunset</figcaption>
</figure>
<figure id="slide2">
    <img decoding="async" src="https://i.pinimg.com/736x/b5/f1/fd/b5f1fdf458910488f3f62484f1a36dfe.jpg" class="">
  <figcaption>An elephant at sunset</figcaption>
</figure>
<figure id="slide3">
    <img decoding="async" src="https://i.pinimg.com/736x/df/77/ff/df77ffc6cc4baf42f36e26b40a3e6237.jpg" class="">
  <figcaption>An elephant at sunset</figcaption>
</figure>
<figure id="slide4">
    <img decoding="async" src="https://i.pinimg.com/1200x/0d/9e/4d/0d9e4dab729f9711e6a685e163e36b39.jpg" class="">
  <figcaption>An elephant at sunset</figcaption>
</figure>
</slider-thumbnails>
<nav>
<button id="sliderprev" type="button"></button>
<button id="slidernext" type="button"></button>
</nav>
</slider-controls>
</slider>

<style>
[hide]{display: none;}
hero img.current{
    opacity: 1;
}

hero img {
    position: absolute;
    top: 0;
    left: 0;
    width: 40%;
    height: 100%;
    object-fit: cover;
    opacity: 0;
    transition: opacity .3s ease-in;
}
hero header {
    position: absolute;
    margin: 2rem;
    z-index: 5;
    color: white;
    width: 200px;
}
slider-thumbnails figure img {
    box-sizing: content-box;
    -o-object-fit: cover;
    object-fit: cover;
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
}

slider-thumbnails figure {
    width: 260px;
    /*height: 50%;*/
    overflow: hidden;
    border-radius: 10px;
    position: relative;
    z-index: 999;
}

slider-thumbnails figcaption {
    position: absolute;
    color: white;
    bottom: 0;
    font-size: .81rem;
    padding: 1rem;
}
slider {
    position: relative;
    display: flex;
    flex-direction: row;
    justify-content: space-between;
    height: 100%;
    background: linear-gradient(90deg, #b827b8, #4c0d4c);
    /*width: 600px;*/
    /*height: 300px;*/
    overflow: hidden;
}

slider:before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: linear-gradient(to bottom, rgba(0, 0, 0, 0.8), rgba(0, 0, 0, 0));
    z-index: 4;
    pointer-events: none;
}
slider-controls {
    padding: 1rem;
    width: 60%;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    justify-content: center;
    gap: 1rem;
}

slider-thumbnails {
    height: 350px;
    display: flex;
    gap: 1rem;
}
slider-controls nav {
    z-index: 9;
    position: relative;
    display: flex;
    flex-direction: row;
    justify-content: center;
    gap: 1rem;
}
slider-controls nav [type="button"]:before{
    content: "\2190";
}
slider-controls nav [type="button"]:last-child:before{
    content: "\2192";
}
slider-controls nav [type="button"] {
    border-radius: 1rem;
    width: 30px;
    height: 30px;
    display: block;
    border: none;
    cursor: pointer;
}

slider-thumbnails figure{
    flex: 0 0 100%;                        
    scroll-snap-align: center;
}
slider-thumbnails {
    overflow-x: scroll;
    scroll-snap-type: x mandatory;
}

</style>