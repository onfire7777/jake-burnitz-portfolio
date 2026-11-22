# Jake Burnitz Portfolio

The source for [jakeburnitz.me](https://jakeburnitz.me/), including featured software projects, BurnFilmz videos, and a site soundtrack.

## Preview locally

From the repository root, run:

```sh
python3 -m http.server 8000 --directory site
```

Open [localhost:8000](http://localhost:8000/). All page assets are local. The soundtrack opens on arrival, selects the middle nine seconds of the official SoundCloud preview, and loops it using the SoundCloud Widget API. If the browser blocks audible autoplay, a click elsewhere on the page or the Play loop control can start the soundtrack. Portfolio videos load when selected.

## Edit and deploy

Edit copy and links in `site/index.html`, theme and layouts in `site/styles.css`, and animation or media controls in `site/portfolio.js`. Cloudflare routing and the static asset directory are configured in `wrangler.toml`.

To publish changes from an authorized Cloudflare account:

```sh
npx wrangler deploy
```
