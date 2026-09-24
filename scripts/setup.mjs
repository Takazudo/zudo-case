import { cp, mkdir, mkdtemp, readFile, readdir, rm, writeFile, access } from "node:fs/promises";
import { createHash } from "node:crypto";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { spawnSync } from "node:child_process";

const defaultRoot = fileURLToPath(new URL("../", import.meta.url));
const defaultCliVersion = "5.27.0";
const exists = async (p) => { try { await access(p); return true; } catch { return false; } };
const json = async (p) => JSON.parse(await readFile(p, "utf8"));
const sha256 = async (p) => createHash("sha256").update(await readFile(p)).digest("hex");

function safeVersion(value) {
  return typeof value === "string" && /^[a-zA-Z0-9.+_-]+$/.test(value) ? value : null;
}

function safeHttpsUrl(value) {
  if (typeof value !== "string") return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" ? url.href : null;
  } catch { return null; }
}

function safeRelativePath(value) {
  if (typeof value !== "string" || path.isAbsolute(value)) return null;
  const segments = value.split(/[\\/]/);
  if (!value || segments.some((segment) => !segment || segment === "." || segment === "..")) return null;
  return /^[a-zA-Z0-9._/-]+$/.test(value) ? segments.join("/") : null;
}

function cleanProvenance(provenance, generated, presetHash, copiedFiles) {
  const cli = provenance.cli && typeof provenance.cli === "object" ? provenance.cli : null;
  const manager = provenance.runtime?.packageManager;
  const packageManager = manager && ["pnpm", "npm", "yarn", "bun"].includes(manager.name)
    ? { name: manager.name, version: safeVersion(manager.version) }
    : null;
  const repository = typeof cli?.repository === "string"
    ? safeHttpsUrl(cli.repository.replace(/^git\+/, "").replace(/\.git$/, ""))
    : null;
  const declaredFrameworkVersion = generated.dependencies?.["@takazudo/zudo-doc"]
    ?? generated.devDependencies?.["@takazudo/zudo-doc"] ?? null;
  const integrity = typeof cli?.integrity === "string" && /^sha512-[A-Za-z0-9+/=]+$/.test(cli.integrity)
    ? cli.integrity : null;
  return {
    schemaVersion: 1,
    completedAt: new Date().toISOString(),
    mode: provenance.mode === "official-cli" ? "official-cli" : "provided-fresh-scaffold",
    cli: cli ? {
      package: "create-zudo-doc",
      requestedVersion: safeVersion(cli.requestedVersion),
      resolvedVersion: safeVersion(cli.resolvedVersion),
      source: {
        repository,
        commit: typeof cli.sourceCommit === "string" && /^[a-f0-9]{40}$/i.test(cli.sourceCommit) ? cli.sourceCommit : null,
        tarball: safeHttpsUrl(cli.tarball),
        integrity,
      },
    } : null,
    runtime: {
      node: safeVersion(provenance.runtime?.node),
      packageManager,
    },
    preset: { file: "setup.preset.json", sha256: presetHash },
    framework: {
      package: "@takazudo/zudo-doc",
      declaredVersion: declaredFrameworkVersion,
      resolvedVersion: null,
      source: null,
    },
    preserved: ["src/content/docs", "public", "engineering", "project", "zfb.config.ts", "README.md", "AGENTS.md"],
    generatedDependencies: generated.dependencies ?? {},
    generatedDevDependencies: generated.devDependencies ?? {},
    copiedFiles: copiedFiles.map((file) => file.split(path.sep).join("/")),
    dependencyInstall: { completed: false, packageManager: null, lockfile: null, resolvedPackages: null },
    actualBuildVerified: false,
  };
}
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
    return ["package.json", "zfb.config.ts", "README.md", "AGENTS.md", "CLAUDE.md", ".gitignore", "pnpm-lock.yaml", "package-lock.json", "yarn.lock", "bun.lockb", "bun.lock"].includes(r)
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
    const setupRecord = cleanProvenance(provenance, generated, await sha256(path.join(root, "setup.preset.json")), targets);
    await writeFile(path.join(root, ".handoff/setup-record.json"), JSON.stringify(setupRecord, null, 2) + "\n");
  } catch (e) {
    for (const p of created) await rm(p, { force: true });
    await writeFile(path.join(root, "package.json"), JSON.stringify(original, null, 2) + "\n");
    throw e;
  }
  return targets;
}

/** Record exact installed package versions and the lockfile after the separate install step. */
export async function recordInstalledSetup(root, options = {}) {
  const recordPath = path.join(root, ".handoff/setup-record.json");
  if (!(await exists(recordPath))) throw new Error("setup-record.jsonがありません。先にscaffoldを取り込んでください。");
  let record = await json(recordPath);
  const project = await json(path.join(root, "package.json"));
  const lockfiles = ["pnpm-lock.yaml", "package-lock.json", "yarn.lock", "bun.lock", "bun.lockb"];
  const lockfileName = await (async () => {
    for (const name of lockfiles) if (await exists(path.join(root, name))) return name;
    return null;
  })();
  if (!lockfileName) throw new Error("依存ロックファイルが見つかりません。先にパッケージをインストールしてください。");
  const managerName = options.packageManager?.name ?? (lockfileName.startsWith("pnpm-") ? "pnpm" : lockfileName === "package-lock.json" ? "npm" : lockfileName.startsWith("yarn") ? "yarn" : "bun");
  const versionResult = options.packageManager?.version
    ? null : spawnSync(managerName, ["--version"], { encoding: "utf8", timeout: 30000 });
  const managerVersion = options.packageManager?.version ?? (versionResult?.status === 0 ? versionResult.stdout.trim() : null);
  const declared = { ...project.dependencies, ...project.devDependencies };
  const resolvedPackages = {};
  for (const name of Object.keys(declared).sort()) {
    const packagePath = path.join(root, "node_modules", ...name.split("/"), "package.json");
    if (!(await exists(packagePath))) throw new Error(`依存が未導入です: ${name}`);
    const installed = await json(packagePath);
    resolvedPackages[name] = installed.version;
  }
  const frameworkManifest = await json(path.join(root, "node_modules", "@takazudo", "zudo-doc", "package.json"));
  if (record.schemaVersion !== 1) {
    const legacyCli = record.mode === "official-cli"
      ? readCliMetadata(record.command === "pnpm" ? "pnpm" : "npm", record.cliVersionRequested ?? defaultCliVersion)
      : null;
    const legacyManager = record.command === "pnpm" ? "pnpm" : "npm";
    record = cleanProvenance({
      mode: record.mode,
      cli: legacyCli,
      runtime: {
        node: options.nodeVersion ?? process.version,
        packageManager: { name: legacyManager, version: packageManagerVersion(legacyManager) },
      },
    }, project, await sha256(path.join(root, "setup.preset.json")), (record.copiedFiles ?? []).filter((file) => file !== "CLAUDE.md"));
  }
  record.runtime = record.runtime?.node
    ? record.runtime
    : { ...record.runtime, node: safeVersion(options.nodeVersion ?? process.version) };
  record.framework = {
    ...record.framework,
    resolvedVersion: resolvedPackages["@takazudo/zudo-doc"] ?? null,
    source: {
      repository: safeHttpsUrl(frameworkManifest.repository?.url?.replace(/^git\+/, "").replace(/\.git$/, "")),
      packagePath: safeRelativePath(frameworkManifest.repository?.directory),
    },
  };
  record.dependencyInstall = {
    completed: true,
    node: safeVersion(options.nodeVersion ?? process.version),
    packageManager: { name: managerName, version: safeVersion(managerVersion) },
    lockfile: { file: lockfileName, sha256: await sha256(path.join(root, lockfileName)) },
    resolvedPackages,
  };
  await writeFile(recordPath, JSON.stringify(record, null, 2) + "\n");
  return record;
}

function readCliMetadata(command, cliVersion) {
  const result = spawnSync(command, ["view", `create-zudo-doc@${cliVersion}`, "version", "repository.url", "gitHead", "dist.tarball", "dist.integrity", "--json"], {
    encoding: "utf8", timeout: 120000,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`公式CLIのnpm provenanceを取得できませんでした: ${result.stderr || result.stdout}`);
  const metadata = JSON.parse(result.stdout);
  if (!metadata.version || !metadata["repository.url"] || !metadata["dist.tarball"] || !metadata["dist.integrity"]) {
    throw new Error("公式CLIのnpm metadataにversion/repository/tarball/integrityがありません。");
  }
  return {
    requestedVersion: cliVersion,
    resolvedVersion: metadata.version,
    repository: metadata["repository.url"],
    sourceCommit: metadata.gitHead,
    tarball: metadata["dist.tarball"],
    integrity: metadata["dist.integrity"],
  };
}

function packageManagerVersion(command) {
  const result = spawnSync(command, ["--version"], { encoding: "utf8", timeout: 30000 });
  if (result.error || result.status !== 0) throw new Error(`${command}のバージョンを取得できません。`);
  return result.stdout.trim();
}

async function main() {
  const args = process.argv.slice(2);
  if (args.includes("--help")) {
    console.log("node scripts/setup.mjs [--dry-run] [--from /path/to/fresh-official-scaffold]\nnode scripts/setup.mjs --record-install\n環境変数: ZUDO_DOC_CLI_VERSION（既定 5.27.0）。作成済みの記事・設定を保持します。");
    return;
  }
  const root = defaultRoot;
  if (args.length === 1 && args[0] === "--record-install") {
    await recordInstalledSetup(root);
    console.log("依存ロックと導入済みパッケージの版を.handoff/setup-record.jsonに記録しました。");
    return;
  }
  const major = Number(process.versions.node.split(".")[0]);
  if (major < 22) throw new Error("Node.js 22以上が必要です。");
  const fromIdx = args.indexOf("--from");
  if (fromIdx !== -1 && !args[fromIdx + 1]) throw new Error("--fromの後に新規scaffoldのパスを指定してください。");
  const allowed = new Set(["--dry-run", "--from"]);
  for (let i = 0; i < args.length; i++) { if (args[i] === "--from") { i++; continue; } if (!allowed.has(args[i])) throw new Error(`不明な引数: ${args[i]}`); }
  const cliVersion = process.env.ZUDO_DOC_CLI_VERSION || defaultCliVersion;
  if (!/^[a-zA-Z0-9.+_-]+$/.test(cliVersion)) throw new Error("CLIバージョンの指定が不正です。");
  if (args.includes("--dry-run")) {
    if (fromIdx !== -1) console.log(`scaffoldを取り込む: ${path.resolve(args[fromIdx + 1])}`);
    else {
      const command = spawnSync("pnpm", ["--version"], { encoding: "utf8" }).status === 0 ? "pnpm" : "npx";
      const prefix = command === "pnpm" ? ["dlx", `create-zudo-doc@${cliVersion}`] : ["--yes", `create-zudo-doc@${cliVersion}`];
      console.log([command, ...prefix, "<temporary-dir>/zudo-case-doc", "--preset", path.join(root, "setup.preset.json"), "--no-install", "--no-git", "--yes"].join(" "));
    }
    return;
  }
  if (await exists(path.join(root, ".handoff/setup-record.json"))) {
    console.log("初期化済みです。pnpm install → node scripts/setup.mjs --record-install → pnpm dev を実行してください。"); return;
  }
  if (fromIdx !== -1) {
    const manager = spawnSync("pnpm", ["--version"], { encoding: "utf8" }).status === 0 ? "pnpm" : "npm";
    await integrateScaffold(root, path.resolve(args[fromIdx + 1]), {
      mode: "provided-fresh-scaffold",
      runtime: { node: process.version, packageManager: { name: manager, version: packageManagerVersion(manager) } },
    });
  } else {
    const pnpmAvailable = spawnSync("pnpm", ["--version"], { encoding: "utf8" }).status === 0;
    const command = pnpmAvailable ? "pnpm" : "npx";
    const prefix = pnpmAvailable ? ["dlx", `create-zudo-doc@${cliVersion}`] : ["--yes", `create-zudo-doc@${cliVersion}`];
    const metadataCommand = pnpmAvailable ? "pnpm" : "npm";
    const cli = readCliMetadata(metadataCommand, cliVersion);
    const managerVersion = packageManagerVersion(metadataCommand);
    const temp = await mkdtemp(path.join(tmpdir(), "zudo-case-doc-"));
    const dest = path.join(temp, "zudo-case-doc");
    const commandArgs = [...prefix, dest, "--preset", path.join(root, "setup.preset.json"), "--no-install", "--no-git", "--yes"];
    console.log("公式CLIで一時scaffoldを生成します。依存のインストールとGit初期化は行いません。");
    try {
      const result = spawnSync(command, commandArgs, { stdio: "inherit", cwd: root, timeout: 600000 });
      if (result.error) throw result.error;
      if (result.status !== 0) throw new Error(`公式CLIが終了コード${result.status}で停止しました。記事は変更していません。接続先とCLIの出力を確認してください。`);
      await integrateScaffold(root, dest, {
        mode: "official-cli",
        cli,
        runtime: { node: process.version, packageManager: { name: metadataCommand, version: managerVersion } },
      });
    } finally { await rm(temp, { recursive: true, force: true }); }
  }
  console.log("初期化完了。次に pnpm install → node scripts/setup.mjs --record-install → pnpm check:docs → pnpm dev を実行してください。公式ビルドはまだ検証していません。");
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  main().catch(e => { console.error(e.stack || e.message); process.exitCode = 1; });
}
