import { printedSidebar } from "./navigation/printed-tree.js";

const section = () => ({ items: [], scopeRoot: "configured" });

export const sidebars = {
  overview: section(),
  "metal-case": section(),
  "printed-5mm": printedSidebar,
  "tenbox-v2": section(),
  "two-way": section(),
  shared: section(),
  development: section(),
};
