import { mayMeasurePageUrl } from './analytics-url.js';

const storageDenied = { ad_Storage: 'denied', analytics_Storage: 'denied' };
let tag;
let active = false;

export function applyClarityPreference(id, enabled) {
  if (!id || active === enabled) return;
  if (!enabled) {
    active = false;
    window.clarity('stop');
    return;
  }
  if (!mayMeasurePageUrl()) return;
  if (tag) {
    // Begin with a fresh project configuration and an empty command queue after withdrawal.
    window.location.reload();
    return;
  }

  active = true;
  window.clarity ??= function () {
    (window.clarity.q ??= []).push(arguments);
  };
  window.clarity('consentv2', storageDenied);
  tag = document.createElement('script');
  tag.async = true;
  tag.referrerPolicy = 'origin';
  tag.src = `https://www.clarity.ms/tag/${id}`;
  tag.addEventListener('error', () => {
    tag.remove();
    tag = undefined;
    active = false;
    if (window.clarity.q) window.clarity.q.length = 0;
  }, { once: true });
  document.head.append(tag);
}

export function trackClarityEvent(name) {
  if (active) window.clarity('event', name);
}
