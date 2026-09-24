import { cp, mkdir, mkdtemp, readFile, readdir, rm, writeFile, access } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { spawnSync } from "node:child_process";

const defaultRoot = fileURLToPath(new URL("../", import.meta.url));
const exists = async (p) => { try { await access(p); return true; } catch { return false; } };
const json = async (p) => JSON.parse(await readFile(p, "utf8"));
async function files(dir, prefix = "") {
  const result = [];
  for (const ent of await readdir(path.join(dir, prefix), { withFileTypes: true })) {
    const rel = path.join(prefix, ent.name);
    if (ent.isSymbolicLink()) throw new Error(`シンボリックリンクは自動コピーしません: ${rel}`);
    if (ent.isDirectory()) {
      if (!["node_modules", ".git", "dist"].includes(ent.name)) result.push(...await files(dir, rel));
    } else result.push(rel);
  }
  return result;
}

/** Merge only framework files. Existing authored content is never overwritten. */
export async function integrateScaffold(root, scaffold, provenance = {}) {
  const generated = await json(path.join(scaffold, "package.json"));
  const original = await json(path.join(root, "package.json"));
  if (!generated.dependencies?.["@takazudo/zudo-doc"] && !generated.devDependencies?.["@takazudo/zudo-doc"]) {
    throw new Error("@takazudo/zudo-docを含む公式scaffoldのpackage.jsonではありません。");
  }
  if (!generated.scripts?.dev || !generated.scripts?.build) throw new Error("公式scaffoldにdev/buildがありません。生成物を確認してください。");
  if (original.dependencies?.["@takazudo/zudo-doc"] || original.devDependencies?.["@takazudo/zudo-doc"]) {
    throw new Error("このフォルダーは初期化済みです。setupで上書きせず、通常のパッケージ更新を行ってください。");
  }
  const skip = (rel) => {
    const r = rel.split(path.sep).join("/");
    return ["package.json", "zfb.config.ts", "README.md", "AGENTS.md", ".gitignore", "pnpm-lock.yaml", "package-lock.json", "yarn.lock", "bun.lockb", "bun.lock"].includes(r)
      || r.startsWith("src/content/docs/") || r.startsWith("src/content/docs-");
  };
  const targets = (await files(scaffold)).filter(r => !skip(r));
  const collisions = [];
  for (const rel of targets) if (await exists(path.join(root, rel))) collisions.push(rel);
  if (collisions.length) throw new Error(`既存ファイルとの衝突。変更せず停止します:\n${collisions.join("\n")}`);

  const created = [];
  try {
    for (const rel of targets) {
      await mkdir(path.dirname(path.join(root, rel)), { recursive: true });
      await cp(path.join(scaffold, rel), path.join(root, rel), { errorOnExist: true, force: false });
      created.push(path.join(root, rel));
    }
    await mkdir(path.join(root, ".handoff"), { recursive: true });
    await writeFile(path.join(root, ".handoff/package.before-setup.json"), JSON.stringify(original, null, 2) + "\n");
    await cp(path.join(scaffold, "zfb.config.ts"), path.join(root, ".handoff/scaffold.zfb.config.ts"));
    const generatedManifest = { ...generated, name: original.name, private: true,
      scripts: { ...original.scripts, ...generated.scripts,
        "setup": "node scripts/setup.mjs", "check:docs": "node scripts/check-docs.mjs",
        "check:assets": "node scripts/verify-assets.mjs", "sync:tables": "node scripts/sync-reference-tables.mjs",
        "test:setup": "node --test tests/setup.test.mjs" } };
    await writeFile(path.join(root, "package.json"), JSON.stringify(generatedManifest, null, 2) + "\n");
    await writeFile(path.join(root, ".handoff/setup-record.json"), JSON.stringify({
      completedAt: new Date().toISOString(), ...provenance,
      preserved: ["src/content/docs", "public", "engineering", "project", "zfb.config.ts", "README.md", "AGENTS.md"],
      generatedDependencies: generated.dependencies ?? {}, generatedDevDependencies: generated.devDependencies ?? {},
      copiedFiles: targets, dependenciesInstalled: false, actualBuildVerified: false,
    }, null, 2) + "\n");
  } catch (e) {
    for (const p of created) await rm(p, { force: true });
    await writeFile(path.join(root, "package.json"), JSON.stringify(original, null, 2) + "\n");
    throw e;
  }
  return targets;
}

async function main() {
  const args = process.argv.slice(2);
  if (args.includes("--help")) {
    console.log("node scripts/setup.mjs [--dry-run] [--from /path/to/fresh-official-scaffold]\n環境変数: ZUDO_DOC_CLI_VERSION（既定 latest）。作成済みの記事・設定を保持します。");
    return;
  }
  const major = Number(process.versions.node.split(".")[0]);
  if (major < 22) throw new Error("Node.js 22以上が必要です。");
  const fromIdx = args.indexOf("--from");
  if (fromIdx !== -1 && !args[fromIdx + 1]) throw new Error("--fromの後に新規scaffoldのパスを指定してください。");
  const allowed = new Set(["--dry-run", "--from"]);
  for (let i = 0; i < args.length; i++) { if (args[i] === "--from") { i++; continue; } if (!allowed.has(args[i])) throw new Error(`不明な引数: ${args[i]}`); }
  const cliVersion = process.env.ZUDO_DOC_CLI_VERSION || "latest";
  if (!/^[a-zA-Z0-9.+_-]+$/.test(cliVersion)) throw new Error("CLIバージョンの指定が不正です。");
  const root = defaultRoot;
  if (await exists(path.join(root, ".handoff/setup-record.json"))) {
    console.log("初期化済みです。pnpm install / pnpm dev を実行してください。"); return;
  }
  if (fromIdx !== -1) {
    if (args.includes("--dry-run")) { console.log(`scaffoldを取り込む: ${path.resolve(args[fromIdx + 1])}`); return; }
    await integrateScaffold(root, path.resolve(args[fromIdx + 1]), { mode: "provided-fresh-scaffold" });
  } else {
    const pnpmAvailable = spawnSync("pnpm", ["--version"], { encoding: "utf8" }).status === 0;
    const command = pnpmAvailable ? "pnpm" : "npx";
    const prefix = pnpmAvailable ? ["dlx", `create-zudo-doc@${cliVersion}`] : ["--yes", `create-zudo-doc@${cliVersion}`];
    if (args.includes("--dry-run")) {
      console.log([command, ...prefix, "<temporary-dir>/zudo-case-doc", "--preset", path.join(root, "setup.preset.json"), "--no-install", "--no-git", "--yes"].join(" "));
      return;
    }
    const temp = await mkdtemp(path.join(tmpdir(), "zudo-case-doc-"));
    const dest = path.join(temp, "zudo-case-doc");
    const commandArgs = [...prefix, dest, "--preset", path.join(root, "setup.preset.json"), "--no-install", "--no-git", "--yes"];
    console.log("公式CLIで一時scaffoldを生成します。依存のインストールとGit初期化は行いません。");
    try {
      const result = spawnSync(command, commandArgs, { stdio: "inherit", cwd: root, timeout: 600000 });
      if (result.error) throw result.error;
      if (result.status !== 0) throw new Error(`公式CLIが終了コード${result.status}で停止しました。記事は変更していません。接続先とCLIの出力を確認してください。`);
      await integrateScaffold(root, dest, { mode: "official-cli", cliVersionRequested: cliVersion, command, commandArgs });
    } finally { await rm(temp, { recursive: true, force: true }); }
  }
  console.log("初期化完了。次に pnpm install → pnpm check:docs → pnpm dev を実行してください。公式ビルドはまだ検証していません。");
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  main().catch(e => { console.error(e.stack || e.message); process.exitCode = 1; });
}
