import { build } from "esbuild";
import { copyFile, mkdir } from "node:fs/promises";

const directory = "site/assets/engine";
await mkdir(directory, { recursive: true });
await build({
  entryPoints: ["artwork/web/spatial-renderer.js"],
  outfile: directory + "/spatial.js",
  bundle: true,
  format: "esm",
  minify: true,
  target: ["es2022"],
  legalComments: "eof",
});
await copyFile("node_modules/three/LICENSE", directory + "/THREE-LICENSE.txt");
