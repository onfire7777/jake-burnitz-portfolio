export const campaignFields = new Set(['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'utm_id']);

export function mayMeasurePageUrl() {
  // Both vendor tags can read the document URL independently of our event fields.
  const url = new URL(window.location.href);
  const knownPage = ['/', '/privacy', '/privacy/', '/privacy.html'].includes(url.pathname);
  if (!knownPage || (url.hash && !document.getElementById(url.hash.slice(1)))) return false;
  for (const [key, value] of url.searchParams) {
    if (!campaignFields.has(key) || !/^[a-z0-9][a-z0-9_-]{0,79}$/i.test(value)) return false;
  }
  if (document.referrer) {
    const referrer = new URL(document.referrer);
    if (referrer.search || referrer.hash) return false;
  }
  return true;
}
