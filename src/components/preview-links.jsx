import { h } from 'preact';
import { previewUrl, previewSourceLabel } from '../../scripts/lib/preview-origin.mjs';
import { previewOrigin } from '../../.cache/preview-origin-override.mjs';

const origin = previewOrigin;

export function PreviewLink({ path, children }) {
  return h('a', { href: previewUrl(path, origin) }, children);
}

export function PreviewFrame({ path, title, height = 720 }) {
  return h('div', null,
    h('iframe', { src: previewUrl(path, origin), title, width: '100%', height, loading: 'lazy', style: { border: '1px solid #6b7280', borderRadius: '8px' } }),
    h('p', null, `表示元: ${previewSourceLabel(origin)}`));
}

export function PreviewSource() {
  return h('p', null, `表示元: ${previewSourceLabel(origin)}`);
}
