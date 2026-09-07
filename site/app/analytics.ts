'use client';

type EventData = Record<string, string | number | boolean>;

declare global {
  interface Window {
    umami?: {
      track: (eventName: string, eventData?: EventData) => void;
    };
  }
}

export function trackEvent(eventName: string, eventData?: EventData) {
  window.umami?.track(eventName, eventData);
}
