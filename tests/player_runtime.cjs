// Execute the generated player offline; only the external media engines are doubled.
const vm = require('node:vm');
const fs = require('node:fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const scripts = [...input.html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)];
const sources = [];
const nodes = new Map();
function node(id) {
  if (!nodes.has(id)) nodes.set(id, {
    textContent: '', style: {}, classList: { toggle() {} }, children: [],
    appendChild(child) { this.children.push(child); },
    addEventListener() {}, play() { return Promise.resolve(); }
  });
  return nodes.get(id);
}
const media = node('vp');
const player = {
  tech: () => ({ el: () => media }), on() {}, one() {},
  src(value) { sources.push({ engine: 'native', url: value.src }); },
  play: () => Promise.resolve()
};
class Hls {
  static isSupported() { return true; }
  static Events = { MANIFEST_PARSED: 'manifest', FRAG_LOADED: 'fragment', ERROR: 'error' };
  loadSource(url) { sources.push({ engine: 'HLS', url }); }
  attachMedia() {} on() {} destroy() {}
}
const context = {
  URL, console: { log() {} }, videojs: () => player, Hls,
  mpegts: {
    isSupported: () => true, Events: { ERROR: 'error' },
    createPlayer({ url }) {
      sources.push({ engine: 'MPEGTS', url });
      return { attachMediaElement() {}, load() {}, play: () => Promise.resolve(),
        on() {}, unload() {}, detachMediaElement() {}, destroy() {} };
    }
  },
  document: { referrer: input.referrer ?? input.page, baseURI: input.page,
    getElementById: node, createElement: () => node(Symbol()) },
  window: { location: new URL('about:srcdoc'), parent: { location: new URL(input.page) },
    isSecureContext: input.page.startsWith('https:') }, location: new URL('about:srcdoc'),
  navigator: {}, setTimeout: () => 1, clearTimeout() {}
};
vm.runInNewContext(scripts.at(-1)[1], context);
process.stdout.write(JSON.stringify({ sources, message: node('pst').textContent }));
