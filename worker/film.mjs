const filmPath = "/assets/signal/studio-film.mp4";

export default {
  async fetch(request, env) {
    const asset = await env.ASSETS.fetch(request);
    if (new URL(request.url).pathname !== filmPath || asset.status !== 200) return asset;

    const headers = new Headers(asset.headers);
    headers.set("Accept-Ranges", "bytes");
    const range = /^bytes=(\d*)-(\d*)$/i.exec(request.headers.get("Range") || "");
    const validator = request.headers.get("If-Range");
    const unchanged = !validator || validator === headers.get("ETag") || validator === headers.get("Last-Modified");
    if (request.method !== "GET" || !range || (!range[1] && !range[2]) || !unchanged) {
      return new Response(asset.body, { headers });
    }

    // This film is 1.35 MB. Slice its versioned asset to supply the exact bytes
    // Safari or Chromium requests when the visitor moves the playhead.
    const data = await asset.arrayBuffer();
    const length = data.byteLength;
    const start = range[1] ? Number(range[1]) : Math.max(0, length - Number(range[2]));
    const end = range[1] && range[2] ? Math.min(Number(range[2]), length - 1) : length - 1;
    if (start > end) {
      headers.set("Content-Range", `bytes */${length}`);
      headers.set("Content-Length", "0");
      return new Response(null, { status: 416, headers });
    }

    headers.set("Content-Range", `bytes ${start}-${end}/${length}`);
    headers.set("Content-Length", String(end - start + 1));
    return new Response(data.slice(start, end + 1), { status: 206, headers });
  },
};
