const config = { key: 'phc_mPnPDQ3mBkMqGYUnAVPyVMj5kRMgwL3mWAw8drjBCrfQ', host: 'https://us.i.posthog.com' };
let client;
let loading;
let allowed = false;

function cleanUrl(value, originOnly = false) {
  if (typeof value !== 'string') return value;
  try {
    const url = new URL(value);
    return originOnly ? url.origin : url.origin + url.pathname;
  } catch {
    return value === '$direct' ? value : undefined;
  }
}

function cleanEvent(event) {
  if (!event?.properties) return event;

  for (const properties of [event.properties, event.properties.$set, event.properties.$set_once]) {
    if (!properties) continue;
    for (const name of Object.keys(properties)) {
      if (name.endsWith('current_url')) properties[name] = cleanUrl(properties[name]);
      if (name.endsWith('referrer')) properties[name] = cleanUrl(properties[name], true);
    }
  }
  const heatmapData = event.properties.$heatmap_data;
  if (heatmapData) {
    const byPage = {};
    for (const [url, points] of Object.entries(heatmapData)) {
      const page = cleanUrl(url);
      if (page) (byPage[page] ??= []).push(...points);
    }
    event.properties.$heatmap_data = byPage;
  }
  return event;
}

export function applyPostHogPreference(enabled) {
  allowed = enabled;
  if (client) {
    if (allowed && client.has_opted_out_capturing()) {
      client.opt_in_capturing({ captureEventName: false });
      client.capture('$pageview');
    } else if (!allowed) {
      client.opt_out_capturing();
    }
    return;
  }

  if (!allowed || loading) return;
  loading = import('./posthog-sdk.js').then(({ default: posthog }) => {
    if (!allowed) return;
    posthog.init(config.key, {
      api_host: config.host,
      persistence: 'memory',
      disable_persistence: true,
      opt_out_persistence_by_default: true,
      person_profiles: 'never',
      capture_pageview: true,
      capture_pageleave: true,
      autocapture: true,
      enable_heatmaps: true,
      disable_session_recording: true,
      disable_surveys: true,
      disable_conversations: true,
      disable_product_tours: true,
      advanced_disable_feature_flags: true,
      mask_all_text: true,
      mask_all_element_attributes: true,
      mask_personal_data_properties: true,
      property_denylist: ['gclid', 'dclid', 'fbclid', 'msclkid', 'wbraid', 'gbraid', 'ttclid', 'twclid', 'li_fat_id', 'mc_cid', 'igshid'],
      before_send: cleanEvent,
    });
    if (posthog.has_opted_out_capturing()) {
      posthog.opt_in_capturing({ captureEventName: false });
    }
    client = posthog;
  }).catch(() => {
    // Analytics availability never controls a site action.
  }).finally(() => {
    loading = undefined;
  });
}

export function trackPostHog(name, properties) {
  if (allowed) client?.capture(name, properties, { send_instantly: true, transport: 'sendBeacon' });
}
