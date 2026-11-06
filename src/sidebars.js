// Editorial sidebars keyed by headerNav categoryMatch (zudo-doc sidebarsConfig).
// Sections without an entry use the automatic directory tree.
// printed-5mm keeps its flat leaf URLs, so its revision groups are explicit here.
export const sidebars = {
  "printed-5mm": [
    { type: "doc", id: "printed-5mm", label: "家庭印刷ケースの入口" },
    {
      type: "category",
      label: "現行 P5（J3差し込み接合）",
      items: [
        "printed-5mm/p5-design",
        "printed-5mm/p5-preview",
        "printed-5mm/p5-print-files",
        { type: "doc", id: "printed-5mm/ventilation", label: "通気孔の仕様（P4から継承）" },
      ],
    },
    { type: "doc", id: "printed-5mm/history", label: "P4・P3の履歴" },
    {
      type: "category",
      label: "履歴 P4（Uniform通気孔）",
      collapsed: true,
      items: ["printed-5mm/p4-design", "printed-5mm/p4-preview", "printed-5mm/p4-print-files"],
    },
    {
      type: "category",
      label: "履歴 P3（通気孔なしの基準）",
      collapsed: true,
      items: ["printed-5mm/design", "printed-5mm/preview", "printed-5mm/print-files"],
    },
  ],
};
