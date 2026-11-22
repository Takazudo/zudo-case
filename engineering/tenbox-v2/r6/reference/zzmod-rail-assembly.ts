import { Matrix4 } from "three";

export type Selection = {
  height: "3U" | "7U";
  width: 40 | 60;
  style: "NY" | "NU";
  color: "WH" | "BK";
};
export type Part = {
  id: string;
  category: "body" | "bar" | "panel" | "nut";
  asset?: string;
  instances?: number[][];
  panel?: "frame3u" | "frame7u" | "pad3u" | "casePad1u";
  matrix: number[];
  explode: [number, number, number];
};
export const initialSelection: Selection = {
  height: "3U",
  width: 40,
  style: "NY",
  color: "WH",
};
export const selections: Selection[] = (["3U", "7U"] as const).flatMap(
  (height) =>
    ([40, 60] as const).flatMap((width) =>
      (["NY", "NU"] as const).flatMap((style) =>
        (["WH", "BK"] as const).map((color) => ({
          height,
          width,
          style,
          color,
        })),
      ),
    ),
);
export function validateSelection(s: Selection) {
  if (!selections.some((x) => productId(x) === productId(s)))
    throw new Error("未対応の構成です");
}
export const productId = (s: Selection) =>
  `RAIL-${s.height}-${s.style}-${s.color}-${s.width}`;
export const bodyMaterial = (s: Selection) =>
  s.color === "WH" ? "9000HE Resin / 白" : "JLC Black Resin / 黒";
export function bom(s: Selection) {
  const rows = s.height === "3U" ? 2 : 6;
  return [
    { name: "single レール本体", count: 2, material: bodyMaterial(s) },
    ...(s.height === "7U"
      ? [{ name: "double レール本体", count: 2, material: bodyMaterial(s) }]
      : []),
    {
      name: s.style === "NY" ? "ナイロンバー" : "スライドナット",
      count: s.style === "NY" ? rows : rows * s.width,
      material:
        s.style === "NY"
          ? "黒 / JLC3DP ナイロン（本体樹脂とは別）"
          : "銀色 / M3 炭素鋼（表示形状は近似）",
    },
    {
      name: `${s.height} side frame`,
      count: 2,
      material: "アルミPCB 1.6 mm / 左右各1枚",
    },
    {
      name: "3U pad",
      count: s.height === "3U" ? 2 : 4,
      material: "アルミPCB 1.6 mm",
    },
    ...(s.height === "7U"
      ? [
          {
            name: "1U pad",
            count: 2,
            material: "アルミPCB 1.6 mm / 中央開口付き",
          },
        ]
      : []),
  ];
}
function matrix(...rows: number[]) {
  return new Matrix4().set(...(rows as Parameters<Matrix4["set"]>)).toArray();
}
export function assembly(s: Selection): Part[] {
  validateSelection(s);
  const L = s.width === 40 ? 204 : 305;
  const is7 = s.height === "7U";
  const center = is7 ? 157.377228 : 67.26593;
  const v = is7 ? 14.9950205 : 15.0303175;
  const endpoints = is7 ? [6.0332935, 308.7211605] : [5.997998, 128.533836];
  const parts: Part[] = [];
  const barLength = s.width === 40 ? 203.203278 : 304.718048;
  const barWidth = s.width === 40 ? 5.503433 : 5.502998;
  function addBar(
    id: string,
    bodyMatrix: number[],
    cavity: [number, number],
    bottom: number,
    explode: [number, number, number],
  ) {
    const local = new Matrix4().set(
      0,
      1,
      0,
      (cavity[0] + cavity[1] - barWidth) / 2,
      0,
      0,
      1,
      bottom,
      1,
      0,
      0,
      (L - barLength) / 2,
      0,
      0,
      0,
      1,
    );
    parts.push({
      id,
      category: "bar",
      asset: `bar-${s.width}hp.stl`,
      matrix: new Matrix4().fromArray(bodyMatrix).multiply(local).toArray(),
      explode,
    });
  }
  function addNuts(
    id: string,
    bodyMatrix: number[],
    single: boolean,
    channel = 0,
    explode: [number, number, number],
  ) {
    const instances = Array.from({ length: s.width }, (_, i) => {
      const position = ((i + 0.5) * L) / s.width;
      const local = single
        ? matrix(
            0,
            0,
            -1,
            6.9,
            1,
            0,
            0,
            6.642464,
            0,
            -1,
            0,
            position,
            0,
            0,
            0,
            1,
          )
        : matrix(
            1,
            0,
            0,
            channel === 0 ? 6.64338 : 18.6972,
            0,
            0,
            1,
            13.232,
            0,
            -1,
            0,
            position,
            0,
            0,
            0,
            1,
          );
      return new Matrix4()
        .fromArray(bodyMatrix)
        .multiply(new Matrix4().fromArray(local))
        .toArray();
    });
    parts.push({
      id,
      category: "nut",
      matrix: new Matrix4().toArray(),
      instances,
      explode,
    });
  }
  for (const [i, u] of endpoints.entries()) {
    const sign = i === 0 ? -1 : 1;
    const y = u - center,
      z = -v;
    const transform =
      s.style === "NU"
        ? matrix(
            0,
            0,
            sign,
            (-sign * L) / 2,
            0,
            sign,
            0,
            y - sign * 6.7535858154296875,
            -1,
            0,
            0,
            z + 14.930564880371094,
            0,
            0,
            0,
            1,
          )
        : matrix(
            0,
            0,
            sign,
            (-sign * L) / 2,
            sign,
            0,
            0,
            y - sign * 5.2001,
            0,
            1,
            0,
            z - 14.42556,
            0,
            0,
            0,
            1,
          );
    parts.push({
      id: `single-${i}`,
      category: "body",
      asset: `${s.style === "NY" ? "nylon" : "nuts"}-single-v3-${s.width}hp.stl`,
      matrix: transform,
      explode: [0, sign * 25, 0],
    });
    if (s.style === "NY")
      addBar(`bar-single-${i}`, transform, [2.300804, 8.131851], 20.716103, [
        0,
        sign * 25,
        32,
      ]);
    else addNuts(`nuts-single-${i}`, transform, true, 0, [0, sign * 25, 32]);
  }
  if (is7) {
    // Case PCB axes retained: new double pitch leaves ~0.08–0.10 mm residual per hole, never stretched.
    for (const [i, pair] of [
      [128.533836, 140.5298535],
      [263.030426, 275.0617065],
    ].entries()) {
      const c =
        s.style === "NY"
          ? (5.197922 + 17.022431) / 2
          : (6.752716 + 18.586121) / 2;
      const transform = matrix(
        0,
        0,
        1,
        -L / 2,
        1,
        0,
        0,
        (pair[0] + pair[1]) / 2 - center - c,
        0,
        1,
        0,
        -v - 5.201429,
        0,
        0,
        0,
        1,
      );
      parts.push({
        id: `double-${i}`,
        category: "body",
        asset: `${s.style === "NY" ? "nylon" : "nuts"}-double-v2-${s.width}hp.stl`,
        matrix: transform,
        explode: [0, 0, -30],
      });
      if (s.style === "NY")
        for (const [j, cavity] of (
          [
            [2.300003, 8.134644],
            [14.092758, 19.923889],
          ] as [number, number][]
        ).entries())
          addBar(
            `bar-double-${i}-${j}`,
            transform,
            cavity,
            11.48938,
            [0, 0, 32],
          );
      else
        for (const j of [0, 1])
          addNuts(`nuts-double-${i}-${j}`, transform, false, j, [0, 0, 32]);
    }
  }
  for (const sign of [-1, 1]) {
    const layers: {
      panel: NonNullable<Part["panel"]>;
      offset: number;
      u: number;
      v: number;
    }[] = [
      { panel: is7 ? "frame7u" : "frame3u", offset: 1.6, u: 0, v: 0 },
      { panel: "pad3u", offset: 0, u: 0, v: 0 },
    ];
    if (is7)
      layers.push(
        { panel: "pad3u", offset: 0, u: 134.53186, v: 0 },
        { panel: "casePad1u", offset: 0, u: 269.039027, v: -0.025081 },
      );
    for (const [i, layer] of layers.entries()) {
      const lowerX = sign * (L / 2 + layer.offset) + (sign < 0 ? -1.6 : 0);
      const transform =
        layer.panel === "frame7u"
          ? matrix(0, 0, 1, lowerX, 0, 1, 0, -center, -1, 0, 0, 0, 0, 0, 0, 1)
          : matrix(
              0,
              0,
              -1,
              lowerX + 1.6,
              1,
              0,
              0,
              layer.u - center,
              0,
              -1,
              0,
              -layer.v,
              0,
              0,
              0,
              1,
            );
      parts.push({
        id: `${layer.panel}-${sign}-${i}`,
        category: "panel",
        panel: layer.panel,
        matrix: transform,
        explode: [sign * (layer.offset ? 55 : 30), 0, 0],
      });
    }
  }
  return parts;
}

