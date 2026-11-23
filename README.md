# Jake Burnitz Portfolio

The source for [jakeburnitz.me](https://jakeburnitz.me/), including articulated 3D studio models, featured software projects, videos from both of Jake’s channels, and the Spotify soundtrack.

## Preview locally

From the repository root, run:

```sh
python3 -m http.server 8000 --directory site
```

Open [localhost:8000](http://localhost:8000/). The site serves its own fonts, models, lighting and artwork. The soundtrack opens on arrival with Spotify’s official player. The browser and Spotify determine autoplay and preview availability. Portfolio videos load when selected.

## Edit and deploy

Edit copy and links in `site/index.html`, theme and layouts in `site/styles.css`, and animation or media controls in `site/portfolio.js`. Cloudflare routing and the static asset directory are configured in `wrangler.toml`.

To publish changes from an authorized Cloudflare account:

```sh
npx wrangler deploy
```

## Studio artwork

The recorder supports horizontal drag, keyboard arrows, and an exploded view. A WebP poster appears first. On supported devices the scene becomes a live 3D model with rotating spindles and an articulated housing. The image turntable remains available if WebGL is unavailable. Reduced motion starts with still artwork and offers explicit control. The posters and recorder geometry come from `artwork/render_studio.py`.

To reproduce the artwork, use Python 3.11 with `bpy==4.5.9` and Pillow. From the repository root, run:

```sh
for scene in recorder voice memory benchmark; do
  python artwork/render_studio.py "$scene" site/assets/studio
done
python artwork/render_studio.py recorder site/assets/studio/recorder --turntable
python artwork/render_studio.py recorder site/assets/studio/recorder --turntable --exploded
```

## Signal Path

The Studio section follows a copper ribbon through a tape reel, a memory stack, and a film gate. Native CSS drives the transitions between chapters. In each visible chapter, WebGL draws the mechanism in three dimensions. The image layers provide a fallback. Reduced-motion and short-screen layouts show the four chapters in reading order. The silent film loads on playback and pauses when it leaves view.

`artwork/build_signal_sources.py` creates the three native SolidCraft designs, the EffectCraft signal traces, and a FilmCraft sequence using the portfolio’s existing video stills. With those three MCP helpers configured in Codex, regenerate the production inputs and render the responsive layers using:

```sh
python3 artwork/build_signal_sources.py "/tmp/signal-path-sources"
python artwork/render_signal.py "/tmp/signal-path-sources" site/assets/signal
```

The live studio film is a separate Gemini-generated macro shot. FilmCraft trims the shot and removes its audio. EffectCraft composites the opening title and animates its fade. The published H.264 edit, poster, and timed visual descriptions are in `site/assets/signal/`.

The full-page installation carries the tape from the opening recorder to the project meters, contact print and seven-socket patch panel. FilmCraft cuts the reel, plate and aperture inserts from the original Gemini film. EffectCraft applies the emulsion and moving light, renders eight exposures, and prints the copper edge that follows the entire page. DesignCraft lays out the three meter faces and VectorCraft draws the JB monogram.

To rebuild the installation, place the original shot at `Gemini Signal Path.mp4` in the Craft project directory and generate the models and traces as above. Then run the following commands with the same directory:

```sh
python artwork/build_signal_sources.py "/tmp/signal-path-sources" --contact-print
python artwork/build_signal_sources.py "/tmp/signal-path-sources" --studio-identity
python artwork/render_signal.py "/tmp/signal-path-sources" site/assets/installation --installation
```


## Live sculpture and lighting

The portfolio sections share an off-white studio surface. Each of the four copper joins returns to the same rail at both ends, including while its mesh flexes. A single WebGL2 renderer draws the visible models into their clipped page canvases. The site fetches models on approach, pauses off-screen scenes, and respects the 3D motion switch, reduced motion, and data-saving preferences.

`artwork/web/spatial-motion.js` articulates the mechanisms. The reel spins around its axle, the memory rack opens along guide rods, and the film advances in its carriage. Focusing an external link moves the cable to that outlet. The filmstrip uses the eight EffectCraft exposures on one curved surface. The surface finish, photographed studio reflections and soft cast shadows use physically based materials. The lighting source is documented in [STUDIO-LIGHT-LICENSE.md](artwork/STUDIO-LIGHT-LICENSE.md).

The deployable models and browser bundle are included in `site/assets/`. To rebuild them, use the same Blender Python environment as the poster render, the original Craft workspace, and Node:

```sh
npm ci
python artwork/export_studio_models.py site/assets/models
python artwork/export_splice_models.py site/assets/models
python artwork/render_signal.py "/path/to/Signal Path" site/assets/models --models
npm run build:spatial
```
