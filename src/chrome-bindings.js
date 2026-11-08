import { routeContext } from "virtual:zudo-doc-route-context";
import { createRouteContext } from "@takazudo/zudo-doc/route-context";
import { createPrintedChrome } from "./navigation/printed-chrome.js";
import { TwoWayTable, TwoWayFrameTable } from "./components/two-way-table.jsx";
import { defineChromeBindings } from "@takazudo/zudo-doc/chrome-bindings";
import { PreviewFrame, PreviewLink, PreviewSource } from "./components/preview-links.jsx";
import { sidebars } from "./sidebars.js";

const baseBindings = defineChromeBindings({
  mdxExtras: { PreviewFrame, PreviewLink, PreviewSource, TwoWayTable, TwoWayFrameTable },
  sidebarsConfig: sidebars,
});

export const chromeBindings = {
  ...baseBindings,
  ...defineChromeBindings(createPrintedChrome(createRouteContext(routeContext), baseBindings)),
};
