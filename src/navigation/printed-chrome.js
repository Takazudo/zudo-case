import { createHeaderWithDefaults } from "@takazudo/zudo-doc/header-with-defaults";
import { createSidebarWithDefaults } from "@takazudo/zudo-doc/sidebar-with-defaults";
import { PRINTED_SECTION, printedSidebar, toPrintedTree } from "./printed-tree.js";

export function createPrintedChrome(routeCtx, bindings) {
  const nativeContext = { ...routeCtx, components: {}, hostBindings: bindings };
  const editorialContext = {
    ...nativeContext,
    hostBindings: {
      ...bindings,
      sidebarsConfig: { ...bindings.sidebarsConfig, [PRINTED_SECTION]: printedSidebar },
    },
    buildNavTree: (...args) => toPrintedTree(routeCtx.buildNavTree(...args)),
  };
  const pair = (context) => ({
    Header: createHeaderWithDefaults(context),
    Sidebar: createSidebarWithDefaults(context),
  });
  const native = pair(nativeContext);
  const editorial = pair(editorialContext);
  const pairFor = (section) => section === PRINTED_SECTION ? editorial : native;

  return {
    Header: (props) => pairFor(props.navSection).Header(props),
    Sidebar: (props) => pairFor(props.navSection).Sidebar(props),
  };
}
