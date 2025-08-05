@filter.jinja:- content
title: Pyonir
menu.group: primary
entries: $dir/pages?limit=15
===
<section class="toc">
<header class="hanken-grotesk-regular">
TABLE OF CONTENT
</header>
<p>"Learn the rules like a pro, so you can break them like an artist." - Pablo Picasso </p>
<ul class="chapters">
{% for p in page.entries %}
  <li class="chapter">
    <span class="title"><a href="{{p.url}}">{{loop.index}}. {{p.title}}</a></span>
    <span class="pgnum">{{p.date.strftime("%b. %d %Y")}}</span>
  </li>
{% endfor %}
</ul>
</section>
<style>
.toc .chapter {
  display: flex;
}
.toc .chapter .title {
  order: 1;
}
.toc .chapter .pgnum {
  order: 3;
}
.toc .chapter::after {
  background-image: radial-gradient(circle, currentcolor 1px, transparent 1.5px);
  background-position: bottom;
  background-size: 1ex 4.5px;
  background-repeat: space no-repeat;
  content: "";
  flex-grow: 1;
  height: 1em;
  order: 2;
}
.toc {
    margin: 3rem auto;
    max-width: 740px;
    & header {
    text-underline-offset: 5px;
    margin-bottom: 3rem; text-decoration: underline; font-size: 2rem;}
}
</style>
