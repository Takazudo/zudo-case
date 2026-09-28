export const PRODUCTION_PREVIEW_ORIGIN = 'https://zudo-case-preview.zudolab.dev';

export function resolvePreviewOrigin({ dev = false, override = '' } = {}) {
  if (override) {
    const url = new URL(override);
    if (!['http:', 'https:'].includes(url.protocol) || url.pathname !== '/' || url.search || url.hash || url.username || url.password)
      throw new Error('ZUDO_CASE_PREVIEW_ORIGIN must be an HTTP(S) origin without a path or credentials');
    return url.origin;
  }
  return dev ? '' : PRODUCTION_PREVIEW_ORIGIN;
}

export function previewUrl(path, origin) {
  if (!/^\/(?:previews|downloads)\/[A-Za-z0-9_./-]+$/.test(path) || path.includes('..'))
    throw new Error(`Invalid preview asset path: ${path}`);
  return `${origin}${path}`;
}

export function previewSourceLabel(origin) {
  return origin ? new URL(origin).host : 'ローカル (public/)';
}

// zfb's embedded V8 config evaluator cannot read Node env; bundle.define reaches SSR and client bundles.
export function previewRunConfig({ root, command, origin }) {
  const buildOutput = command !== 'dev';
  return `import config from ${JSON.stringify(`${root}/zfb.config.ts`)};
export default {
  ...config,
  outDir: ${buildOutput ? `(config.outDir?.startsWith('/') ? config.outDir : ${JSON.stringify(`${root}/`)} + (config.outDir || 'dist'))` : "'dist'"},
  bundle: {
    ...config.bundle,
    define: { ...config.bundle?.define, __ZUDO_CASE_PREVIEW_ORIGIN__: ${JSON.stringify(JSON.stringify(origin))} },
  },
};
`;
}
