import { campaignFields, mayMeasurePageUrl } from './analytics-url.js';

const denied = {
  analytics_storage: 'denied',
  ad_storage: 'denied',
  ad_user_data: 'denied',
  ad_personalization: 'denied',
};

let allowed = false;
let initialized = false;
let script;
let withdrawn = false;

function gtag() {
  window.dataLayer.push(arguments);
}

function configureTag(id) {
  window.dataLayer ??= [];
  gtag('consent', 'default', { region: ['US'], analytics_storage: 'granted' });
  gtag('consent', 'default', denied);
  gtag('set', 'ads_data_redaction', true);

  const settings = {
    cookie_domain: 'none',
    cookie_path: '/',
    cookie_expires: 365 * 24 * 60 * 60,
    cookie_flags: 'SameSite=Lax;Secure',
    allow_google_signals: false,
    allow_ad_personalization_signals: false,
    page_location: analyticsPageUrl(),
    page_referrer: document.referrer ? new URL(document.referrer).origin : '',
    page_title: document.title,
  };
  gtag('js', new Date());
  gtag('set', settings);
  // Let the web stream's config send its one initial pageview.
  gtag('config', id, settings);
}

function analyticsPageUrl() {
  const current = new URL(window.location.href);
  const page = new URL(current.pathname, current.origin);
  for (const name of campaignFields) {
    const value = current.searchParams.get(name);
    if (value && /^[a-z0-9][a-z0-9_-]{0,79}$/i.test(value)) page.searchParams.set(name, value);
  }
  return page.href;
}

function clearMeasurementCookies(id) {
  const names = ['_ga', '_ga_' + id.slice(2)];
  try {
    const present = new Set(document.cookie.split(';').map(cookie => cookie.trim().split('=')[0]));
    for (const name of names) {
      if (!present.has(name)) continue;
      const expired = name + '=; Path=/; Max-Age=0; SameSite=Lax; Secure';
      document.cookie = expired;
      // Also remove a legacy cookie written on the parent domain by Google's automatic configuration.
      document.cookie = expired + '; Domain=jakeburnitz.me';
    }
  } catch {
    // Some browsers disable access to cookies altogether.
  }
}

export function applyGoogleAnalyticsPreference(id, next) {
  if (!id) return;
  allowed = next && mayMeasurePageUrl();
  window[`ga-disable-${id}`] = !allowed;
  if (!next) {
    if (initialized && !withdrawn) {
      withdrawn = true;
      gtag('consent', 'update', denied);
    }
    clearMeasurementCookies(id);
    return;
  }
  if (!allowed) return;
  if (withdrawn) {
    window.location.reload();
    return;
  }
  if (script) return;

  // Queue consent and page settings before the SDK can process its first hit.
  if (!initialized) {
    configureTag(id);
    initialized = true;
  }
  script = document.createElement('script');
  script.async = true;
  script.referrerPolicy = 'origin';
  script.src = `https://www.googletagmanager.com/gtag/js?id=${id}`;
  script.addEventListener('error', () => {
    script.remove();
    script = undefined;
  }, { once: true });
  document.head.append(script);
}

export function trackGoogleAnalyticsEvent(id, name, properties) {
  if (!id || !allowed || !script) return;
  gtag('event', name, { ...properties, send_to: id });
}
