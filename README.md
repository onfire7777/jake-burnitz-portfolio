# Jake Burnitz Portfolio

The source for [jakeburnitz.me](https://jakeburnitz.me/), including featured software projects, BurnFilmz videos, and a site soundtrack.

## Preview locally

From the repository root, run:

```sh
python3 -m http.server 8000 --directory site
```

Open [localhost:8000](http://localhost:8000/). All page assets are local. The soundtrack widget opens on arrival and offers the official Spotify preview. Portfolio videos load when selected.

## Edit and deploy

Edit copy and links in `site/index.html`, theme and layouts in `site/styles.css`, and animation or media controls in `site/portfolio.js`. Cloudflare routing and the static asset directory are configured in `wrangler.toml`.

To publish changes from an authorized Cloudflare account:

```sh
npx wrangler deploy
```

## Soundtrack clips

To enable the site’s native looping player, add audio clips cleared for public playback to `site/assets/` and list their URLs in `soundtrackClips` in `site/portfolio.js`. The player selects one clip per page load and loops it. If the browser blocks audible autoplay, the Play button starts the selected clip.
