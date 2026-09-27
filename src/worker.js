import largeAssets from "../.worker-build/large-assets.json" with { type: "json" };
import { createWorker } from "./worker-handler.js";

export default createWorker(largeAssets);
