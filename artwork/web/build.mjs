import { build } from "esbuild";
import { copyFile, mkdir, readFile, readdir } from "node:fs/promises";

const directory = "site/assets/engine";
await mkdir(directory, { recursive: true });
const options = {
  bundle: true,
  minify: true,
  target: ["es2022"],
  legalComments: "eof",
};
await build({
  ...options,
  entryPoints: ["artwork/web/spatial-renderer.js"],
  outfile: directory + "/spatial.js",
  format: "esm",
});
await copyFile("node_modules/three/LICENSE", directory + "/THREE-LICENSE.txt");

// file:// cannot fetch neighboring ES modules or binary models. For the
// double-click preview, package those inputs with the original renderer.
const models = (await readdir("site/assets/models")).filter(name => name.endsWith(".glb")).sort();
const paths = ["/assets/engine/studio-light.hdr", ...models.map(name => "/assets/models/" + name)];
const resources = {};
for (const path of paths) {
  const data = await readFile("site" + path);
  resources[path] = "data:application/octet-stream;base64," + data.toString("base64");
}
await build({
  ...options,
  format: "iife",
  outfile: "site/file-preview/spatial.js",
  stdin: {
    resolveDir: process.cwd(),
    contents: `
      import { DefaultLoadingManager } from "three";
      const resources = ${JSON.stringify(resources)};
      DefaultLoadingManager.setURLModifier(url => resources[url] ?? url);
      require("./artwork/web/spatial-renderer.js");
    `,
  },
});
