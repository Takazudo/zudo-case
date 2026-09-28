import { h } from 'preact';
import { previewUrl, previewSourceLabel, PRODUCTION_PREVIEW_ORIGIN } from '../../scripts/lib/preview-origin.mjs';

const origin = typeof __ZUDO_CASE_PREVIEW_ORIGIN__ === 'undefined'
  ? PRODUCTION_PREVIEW_ORIGIN : __ZUDO_CASE_PREVIEW_ORIGIN__;

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
