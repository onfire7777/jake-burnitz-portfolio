# Jake Burnitz Portfolio

The source for [jakeburnitz.me](https://jakeburnitz.me/), including featured software projects, BurnFilmz videos, and an optional Spotify soundtrack.

## Preview locally

From the repository root, run:

```sh
python3 -m http.server 8000 --directory site
```

Open [localhost:8000](http://localhost:8000/). All page assets are local. YouTube and Spotify load their players only after a visitor opens them.

## Edit and deploy

Edit copy and links in `site/index.html`, theme and layouts in `site/styles.css`, and animation or media controls in `site/portfolio.js`. Cloudflare routing and the static asset directory are configured in `wrangler.toml`.

To publish changes from an authorized Cloudflare account:

```sh
npx wrangler deploy
```

Fonts are distributed under their included licenses. The featured video and soundtrack play through their respective platform embeds.
