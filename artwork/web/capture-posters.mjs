// Serve site/ after npm run build:spatial. A local playwright-core installation
// and Chromium browser are enough. Example from the repository root:
// PLAYWRIGHT_MODULE=/absolute/path/to/playwright-core/index.mjs CHROME_BIN=/path/to/chrome node artwork/web/capture-posters.mjs http://localhost:8000/
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || "playwright-core");
const source = new URL(process.argv[2] || "http://localhost:8000/");
const directory = fileURLToPath(new URL("../../site/assets/posters/", import.meta.url));
const subjects = [
  ["recorder", ".opening", 1200], ["spool", "#signal-voice", 1360],
  ["plates", "#signal-memory", 1360], ["gate", "#signal-frame", 1360],
  ["burnos", "#work", 800], ["mnemosyne", "#work", 800], ["mnemetric", "#work", 800],
  ["contact", "#videos", 1280], ["patch", "#links", 900],
];
// Append model names after the URL to regenerate just those subjects.
const selected = new Set(process.argv.slice(3));
const browser = await chromium.launch({ executablePath: process.env.CHROME_BIN });
try {
  await mkdir(directory, { recursive: true });
  for (const [name, anchor, width] of subjects) {
    if (selected.size && !selected.has(name)) continue;
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
    // Hold the engine until each shot is prepared. Keep third-party players
    // out of an offline export. All materials and meshes come from this site.
    await page.route("**/*", route => {
      const url = new URL(route.request().url());
      if (url.pathname.endsWith("/spatial-loader.js")) return route.fulfill({ contentType: "text/javascript", body: "" });
      if (url.origin !== source.origin && url.protocol.startsWith("http")) return route.abort();
      return route.continue();
    });
    await page.goto(source.href, { waitUntil: "domcontentloaded" });
    await page.evaluate(() => document.fonts.ready);
    const ratio = await page.evaluate(({ name, anchor }) => {
      const mount = document.querySelector('[data-model="' + name + '"]');
      const measured = mount.clientHeight / mount.clientWidth;
      // The negative can fill a taller mobile mast. Render the extra film
      // above and below center while preserving the camera's horizontal scale.
      const ratio = name === "contact" ? Math.max(.37, measured) : measured;
      document.querySelectorAll("[data-model]").forEach(other => {
        if (other !== mount) other.style.setProperty("translate", "12000px 0", "important");
      });
      document.querySelector(anchor).scrollIntoView({ behavior: "instant", block: "start" });
      // A single studio instrument can use the engine's full Retina buffer.
      // Keep the real page's camera aspect and avoid clipping any shadow.
      if (name === "contact") mount.style.setProperty("height", Math.round(mount.clientWidth * ratio) + "px", "important");
      if (mount.clientWidth < 520) {
        mount.style.setProperty("width", "520px", "important");
        mount.style.setProperty("height", Math.round(520 * ratio) + "px", "important");
      }
      return ratio;
    }, { name, anchor });
    await page.evaluate(() => import("/assets/engine/spatial.js").then(() => undefined));
    const canvas = page.locator('[data-model="' + name + '"].has-live-model > canvas');
    await canvas.waitFor({ timeout: 18000 });
    // The shared WebGL buffer may be a different aspect to the element.
    // Resampling into the element's logical frame restores the real view.
    for (const [filename, outputWidth] of [[name, width], ...(name === "recorder" ? [["recorder-small", 540]] : [])]) {
      const image = await canvas.evaluate((canvas, { outputWidth, ratio }) => {
        const result = document.createElement("canvas");
        result.width = outputWidth;
        result.height = Math.round(outputWidth * ratio);
        const context = result.getContext("2d");
        context.imageSmoothingQuality = "high";
        context.drawImage(canvas, 0, 0, result.width, result.height);
        return result.toDataURL("image/webp", .9).split(",")[1];
      }, { outputWidth, ratio });
      const bytes = Buffer.from(image, "base64");
      if (bytes.length < 1500) throw Error("Empty poster for " + filename);
      await writeFile(directory + filename + ".webp", bytes);
      console.log(filename, outputWidth + "×" + Math.round(outputWidth * ratio), bytes.length + " B");
    }
    await page.close();
  }
} finally { await browser.close(); }
