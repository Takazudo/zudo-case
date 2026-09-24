import { defineConfig } from "zfb/config";
import { zudoDoc } from "@takazudo/zudo-doc/config";

// Official scaffold supplies its package pins, routes, and base CSS at setup time.
// This file owns only the documentation project's settings.
export default defineConfig(
  zudoDoc({
    siteName: "ZUDO CASE",
    siteDescription: "金属平板ケース３機種の設計・検証・見積・発注準備。採用仕様と製作データの状態を分けて管理する。",
    defaultLocale: "ja",
    locales: {},
    base: "/",
    entryDocSlug: "overview/start",
    noindex: true,
    logo: false,
    githubUrl: false,
    editUrl: false,
    cjkFriendly: true,
    sidebarResizer: true,
    sidebarToggle: true,
    tocToggle: true,
    imageEnlarge: true,
    assetViewer: false,
    dynamicPageTransition: false,
    docHistory: false,
    docMetainfo: false,
    headerNav: [
      { label: "概要", path: "/docs/overview", categoryMatch: "overview" },
      { label: "機種", path: "/docs/models", categoryMatch: "models" },
      { label: "設計", path: "/docs/design", categoryMatch: "design" },
      { label: "製作", path: "/docs/manufacturing", categoryMatch: "manufacturing" },
      { label: "検証", path: "/docs/verification", categoryMatch: "verification" },
      { label: "資料", path: "/docs/resources", categoryMatch: "resources" },
      { label: "履歴", path: "/docs/decisions", categoryMatch: "decisions" },
      { label: "引継ぎ", path: "/docs/handoff", categoryMatch: "handoff" },
    ],
    headerRightItems: [
      { type: "component", component: "theme-toggle" },
      { type: "component", component: "search" },
    ],
  }),
);
