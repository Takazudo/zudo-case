export function createWorker(largeAssets) {
  return {
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
      let streamedBytes = 0;
      const stream = new ReadableStream({
        async pull(controller) {
          try {
            while (true) {
              if (!reader) {
                if (index === asset.chunks.length) {
                  if (streamedBytes !== asset.size) {
                    controller.error(
                      new Error(`Asset stream size mismatch: expected ${asset.size}, received ${streamedBytes}`),
                    );
                    return;
                  }
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
              streamedBytes += value.byteLength;
              if (streamedBytes > asset.size) {
                throw new Error(`Asset stream size mismatch: expected ${asset.size}, received ${streamedBytes}`);
              }
              // This guard detects truncation/length drift; same-length corruption is caught by the deployed SHA-256 verifier.
              controller.enqueue(value);
              return;
            }
          } catch (error) {
            controller.error(error);
            await reader?.cancel(error).catch(() => {});
            reader?.releaseLock();
            reader = undefined;
          }
        },
        cancel(reason) {
          return reader?.cancel(reason);
        },
      });
      return new Response(stream, { headers });
    },
  };
}
