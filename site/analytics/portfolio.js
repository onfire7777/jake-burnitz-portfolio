import { applyPostHogPreference, trackPostHog } from './posthog.js';
import { applyGoogleAnalyticsPreference, trackGoogleAnalyticsEvent } from './google-analytics.js';
import { applyClarityPreference, trackClarityEvent } from './microsoft-clarity.js';
import { mayMeasurePageUrl } from './analytics-url.js';

const measurement = 'G-VH844WB1QE';
const preference = 'portfolio.analytics.disabled';
const control = document.querySelector('[data-analytics-control]');
const production = ['jakeburnitz.me', 'www.jakeburnitz.me'].includes(location.hostname);
const privacySignal = navigator.globalPrivacyControl === true;
let enabled = false;

function setEnabled(next) {
  enabled = next && !privacySignal && mayMeasurePageUrl();
  applyPostHogPreference(enabled);
  applyGoogleAnalyticsPreference(measurement, enabled);
  applyClarityPreference('zjtarzlnap', enabled);
  control.textContent = privacySignal ? 'Analytics off (privacy signal)' : next ? 'Turn analytics off' : 'Turn analytics on';
}

function track(name, fields) {
  if (!enabled || !mayMeasurePageUrl()) return;
  trackPostHog(name, fields);
  trackGoogleAnalyticsEvent(measurement, name, fields);
  trackClarityEvent(name);
}

if (production && control) {
  control.hidden = false;
  control.disabled = privacySignal;
  let optedOut = true;
  try { optedOut = localStorage.getItem(preference) === '1'; } catch {}
  setEnabled(!optedOut);
  control.addEventListener('click', () => {
    const next = control.textContent === 'Turn analytics on';
    try { localStorage.setItem(preference, next ? '0' : '1'); } catch {}
    setEnabled(next);
  });
  window.addEventListener('storage', event => {
    if (event.key === preference) setEnabled(event.newValue !== '1');
  });
  document.addEventListener('click', event => {
    const el = event.target.closest?.('a,button');
    if (!el) return;
    const section = el.closest('section')?.id || 'opening';
    if (el.matches('[data-video]')) {
      track('portfolio_video_select', { video_id: new URL(el.href).searchParams.get('v'), section });
    } else if (el.matches('[data-side]')) {
      track('portfolio_side_select', { side: el.dataset.side });
    } else if (el.matches('.sound-trigger')) {
      track('portfolio_soundtrack_select', {});
    } else if (el.matches('a[href^="https://"]')) {
      const link = new URL(el.href);
      track('portfolio_link_click', { destination: link.hostname, link_path: link.pathname, section });
    }
  }, true);
  const sections = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (entry.isIntersecting && enabled) {
        track('portfolio_section_view', { section: entry.target.id });
        sections.unobserve(entry.target);
      }
    }
  }, { rootMargin: '0px 0px -20% 0px' });
  document.querySelectorAll('main section[id]').forEach(section => sections.observe(section));
}
