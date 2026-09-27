import { defineChromeBindings } from "@takazudo/zudo-doc/chrome-bindings";
import { PreviewFrame, PreviewLink, PreviewSource } from "./components/preview-links.jsx";

export const chromeBindings = defineChromeBindings({
  mdxExtras: { PreviewFrame, PreviewLink, PreviewSource },
});
