# Jake Burnitz Portfolio

The source for [jakeburnitz.me](https://jakeburnitz.me/), including original 3D studio artwork, featured software projects, videos from both of Jake’s channels, and the Spotify soundtrack.

## Preview locally

From the repository root, run:

```sh
python3 -m http.server 8000 --directory site
```

Open [localhost:8000](http://localhost:8000/). All page assets are local. The soundtrack opens on arrival with Spotify’s official player. The browser and Spotify determine autoplay and preview availability. Portfolio videos load when selected.

## Edit and deploy

Edit copy and links in `site/index.html`, theme and layouts in `site/styles.css`, and animation or media controls in `site/portfolio.js`. Cloudflare routing and the static asset directory are configured in `wrangler.toml`.

To publish changes from an authorized Cloudflare account:

```sh
npx wrangler deploy
```

## Studio artwork

The recorder supports horizontal drag, keyboard arrows, and an exploded view. The page loads a WebP poster on arrival. Additional angles load on interaction. Project illustrations and recorder geometry are generated offline by `artwork/render_studio.py`.

To reproduce the artwork, use Python 3.11 with `bpy==4.5.9` and Pillow. From the repository root, run:

```sh
for scene in recorder voice memory benchmark; do
  python artwork/render_studio.py "$scene" site/assets/studio
done
python artwork/render_studio.py recorder site/assets/studio/recorder --turntable
python artwork/render_studio.py recorder site/assets/studio/recorder --turntable --exploded
```
