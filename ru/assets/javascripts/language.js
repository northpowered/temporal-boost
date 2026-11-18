// Language changes use normal navigation so lang and the native search worker reload together.
document.addEventListener("click", (event) => {
  const link = event.target.closest("a[data-portal-language]");
  if (!link || !location.hash) return;
  let fragment;
  try { fragment = decodeURIComponent(location.hash.slice(1)); } catch { return; }
  if (link.dataset.anchorIds.split(" ").includes(fragment)) link.hash = location.hash;
});

// Zensical 0.1.0 localizes the index but hardcodes the new search dialog's labels.
// Adapt those labels inside its open shadow root; all copy comes from the manifest.
const searchI18n = JSON.parse(document.getElementById("portal-search-i18n").textContent);
const observedSearchRoots = new WeakSet();
function localizeSearch(root) {
  const translate = (text) => {
    const count = text.match(/^([\d,]+) results?$/);
    return searchI18n.strings[text] || (count && searchI18n.count ? searchI18n.count.replace("{count}", count[1]) : text);
  };
  for (const element of root.querySelectorAll("[aria-label], [placeholder]")) {
    for (const attr of ["aria-label", "placeholder"]) {
      const old = element.getAttribute(attr);
      if (old && translate(old) !== old) element.setAttribute(attr, translate(old));
    }
  }
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (node.parentElement?.tagName === "STYLE") continue;
    const translated = translate(node.textContent);
    if (translated !== node.textContent) node.textContent = translated;
  }
}
function findSearchRoots() {
  for (const element of document.body.children) {
    const root = element.shadowRoot;
    if (!root || observedSearchRoots.has(root)) continue;
    observedSearchRoots.add(root);
    localizeSearch(root);
    new MutationObserver(() => localizeSearch(root)).observe(root, {
      subtree: true, childList: true, characterData: true,
      attributes: true, attributeFilter: ["aria-label", "placeholder"],
    });
  }
}
findSearchRoots();
new MutationObserver(findSearchRoots).observe(document.body, { childList: true });
