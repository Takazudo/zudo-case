import largeAssets from "../.worker-build/large-assets.json" with { type: "json" };

export default {
  async fetch(request, env) {
    const path = new URL(request.url).pathname;
    const asset = largeAssets[path];
    if (!asset) return env.ASSETS.fetch(request);
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response(null, { status: 405, headers: { Allow: "GET, HEAD" } });
    }

    const headers = {
      "Content-Type": asset.type,
      "Content-Length": String(asset.size),
      ETag: `"${asset.hash}"`,
    };
    if (request.method === "HEAD") return new Response(null, { headers });

    let index = 0;
    let reader;
    const stream = new ReadableStream({
      async pull(controller) {
        try {
          while (true) {
            if (!reader) {
              if (index === asset.chunks.length) {
                controller.close();
                return;
              }
              const url = new URL(asset.chunks[index++], request.url);
              const response = await env.ASSETS.fetch(new Request(url));
              if (!response.ok || !response.body) {
                throw new Error(`Unable to read asset chunk: ${url.pathname}`);
              }
              reader = response.body.getReader();
            }
            const { done, value } = await reader.read();
            if (done) {
              reader.releaseLock();
              reader = undefined;
              continue;
            }
            controller.enqueue(value);
            return;
          }
        } catch (error) {
          controller.error(error);
        }
      },
      cancel() {
        return reader?.cancel();
      },
    });
    return new Response(stream, { headers });
  },
};
