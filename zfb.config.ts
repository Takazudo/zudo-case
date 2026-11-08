import { defineConfig } from "zfb/config";
import { zudoDoc } from "@takazudo/zudo-doc/config";

// Official scaffold supplies its package pins, routes, and base CSS at setup time.
// This file owns only the documentation project's settings.
export default defineConfig(
  zudoDoc({
    themePack: "default",
    siteName: "ZUDO CASE",
    siteDescription: "モジュール用ケースの独立した設計系列（金属ケース、7U40家庭印刷、10BOX-v2、2WAY実験設計）と共通部品の設計・検証・発注準備。採用仕様と製作データの状態を分けて管理する。",
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
    assetViewer: true,
    assetViewerIndex: true,
    chromeBindingsModule: "./src/chrome-bindings.js",
    dynamicPageTransition: false,
    docHistory: false,
    docMetainfo: false,
    headerNav: [
      {
        label: "ケース", path: "/docs/overview/start", categoryMatch: "overview",
        children: [
          { label: "金属ケース", path: "/docs/metal-case", categoryMatch: "metal-case" },
          { label: "7U40家庭印刷", path: "/docs/printed-5mm", categoryMatch: "printed-5mm" },
          { label: "10BOX-v2", path: "/docs/tenbox-v2", categoryMatch: "tenbox-v2" },
          { label: "2WAY", path: "/docs/two-way", categoryMatch: "two-way" },
        ],
      },
      { label: "共通部品", path: "/docs/shared", categoryMatch: "shared" },
      { label: "開発・保守", path: "/docs/development", categoryMatch: "development" },
      { label: "画像・図", path: "/files", versioned: false },
    ],
    headerRightItems: [
      { type: "component", component: "theme-toggle" },
      { type: "component", component: "search" },
    ],
  }),
);
