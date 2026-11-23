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

The recorder supports horizontal drag, keyboard arrows, and an exploded view. The page loads a WebP poster on arrival. Additional angles load on interaction. Native CSS scroll timelines tilt the recorder, move the studio illustrations, and draw the reading progress line. Reduced motion keeps the artwork stationary. Project illustrations and recorder geometry are generated offline by `artwork/render_studio.py`.

To reproduce the artwork, use Python 3.11 with `bpy==4.5.9` and Pillow. From the repository root, run:

```sh
for scene in recorder voice memory benchmark; do
  python artwork/render_studio.py "$scene" site/assets/studio
done
python artwork/render_studio.py recorder site/assets/studio/recorder --turntable
python artwork/render_studio.py recorder site/assets/studio/recorder --turntable --exploded
```

## Signal Path

The Studio section follows a copper ribbon through a tape reel, a memory stack, and a film gate. Each scene has independently moving layers driven by the native CSS scroll timeline. Reduced-motion and short-screen layouts show the four chapters in reading order. The silent film loads on playback and pauses when it leaves view.

`artwork/build_signal_sources.py` creates the three native SolidCraft designs, the EffectCraft signal traces, and a FilmCraft sequence using the portfolio’s existing video stills. With those three MCP helpers configured in Codex, regenerate the production inputs and render the responsive layers using:

```sh
python3 artwork/build_signal_sources.py "/tmp/signal-path-sources"
python artwork/render_signal.py "/tmp/signal-path-sources" site/assets/signal
```

The live studio film is a separate Gemini-generated macro shot. FilmCraft trims the shot and removes its audio. EffectCraft composites the opening title and animates its fade. The published H.264 edit, poster, and timed visual descriptions are in `site/assets/signal/`.
