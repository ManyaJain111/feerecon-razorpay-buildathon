// Firebase Web SDK initialization with Analytics only
// Config is fetched from /api/auth/firebase-config at runtime to avoid hardcoding

let firebaseApp = null;
let firebaseAnalytics = null;

async function initAnalytics() {
  // Load config from backend
  const res = await fetch('/api/auth/firebase-config');
  const config = await res.json();

  // Import SDKs
  const { initializeApp } = await import('https://www.gstatic.com/firebasejs/12.19.0/firebase-app.js');
  const { getAnalytics, logEvent } = await import('https://www.gstatic.com/firebasejs/12.19.0/firebase-analytics.js');

  firebaseApp = initializeApp(config);
  firebaseAnalytics = getAnalytics(firebaseApp);

  // Track page view
  logEvent(firebaseAnalytics, 'page_view', { page_location: location.href });

  return { firebaseApp, firebaseAnalytics, logEvent };
}

// Auto-initialize on load
initAnalytics().catch(console.error);

// Expose globally for manual use
window.FirebaseInit = { initAnalytics, getApp: () => firebaseApp, getAnalytics: () => firebaseAnalytics };
