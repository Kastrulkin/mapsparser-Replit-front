(function () {
  "use strict";

  try {
    var script = document.currentScript;
    if (!script) return;
    var trackerId = script.getAttribute("data-business") || "";
    if (trackerId.indexOf("pub_") !== 0) return;
    var trackerVersion = "1.2.2";
    var schemaVersion = 2;
    var maxQueueSize = 100;
    var apiOrigin = new URL(script.src, window.location.href).origin;
    var endpoint = apiOrigin + "/api/tracking/events";
    var consent = script.getAttribute("data-consent") !== "denied" && window.localosTrackingConsent !== false;
    var queue = [];
    var flushTimer = 0;
    var heartbeatTimer = 0;
    var foregroundStartedAt = 0;
    var pageDepths = {};
    var lastPageViewKey = "";
    var lastPageViewAt = 0;
    var startedForms = typeof WeakSet === "function" ? new WeakSet() : null;

    function randomId(prefix) {
      var bytes = new Uint8Array(12);
      if (window.crypto && window.crypto.getRandomValues) window.crypto.getRandomValues(bytes);
      else for (var i = 0; i < bytes.length; i += 1) bytes[i] = Math.floor(Math.random() * 256);
      var value = "";
      for (var j = 0; j < bytes.length; j += 1) value += bytes[j].toString(16).padStart(2, "0");
      return prefix + value;
    }

    function storedId(storage, key, prefix) {
      try {
        var current = storage.getItem(key);
        if (current && current.indexOf(prefix) === 0) return current;
        current = randomId(prefix);
        storage.setItem(key, current);
        return current;
      } catch (_error) {
        return randomId(prefix);
      }
    }

    var visitorId = consent ? storedId(window.localStorage, "localos_visitor_id", "v_") : "";
    var sessionId = consent ? storedId(window.sessionStorage, "localos_session_id", "s_") : "";

    function page() {
      return { hostname: window.location.hostname, path: window.location.pathname || "/", title: document.title || "" };
    }
    var activePage = page();

    function utm() {
      var params = new URLSearchParams(window.location.search);
      return {
        source: params.get("utm_source") || "",
        medium: params.get("utm_medium") || "",
        campaign: params.get("utm_campaign") || "",
        term: params.get("utm_term") || "",
        content: params.get("utm_content") || ""
      };
    }

    function deviceType() {
      if (window.innerWidth < 768) return "mobile";
      if (window.innerWidth < 1100) return "tablet";
      return "desktop";
    }

    function enqueue(eventName, extra) {
      if (!consent) return;
      if (!visitorId) visitorId = storedId(window.localStorage, "localos_visitor_id", "v_");
      if (!sessionId) sessionId = storedId(window.sessionStorage, "localos_session_id", "s_");
      var event = {
        event_id: randomId("e_"),
        visitor_id: visitorId,
        session_id: sessionId,
        event: eventName,
        timestamp: new Date().toISOString(),
        page: page(),
        referrer: document.referrer || "",
        utm: utm(),
        device_type: deviceType()
      };
      if (extra) for (var key in extra) if (Object.prototype.hasOwnProperty.call(extra, key)) event[key] = extra[key];
      queue.push(event);
      if (queue.length > maxQueueSize) queue.splice(0, queue.length - maxQueueSize);
      if (queue.length >= 10) flush(false);
      else if (!flushTimer) flushTimer = window.setTimeout(function () { flush(false); }, 5000);
    }

    function flush(useBeacon) {
      if (flushTimer) window.clearTimeout(flushTimer);
      flushTimer = 0;
      if (!queue.length || !consent) return;
      var batch = queue.splice(0, 25);
      var body = JSON.stringify({ tracker_id: trackerId, tracker_version: trackerVersion, schema_version: schemaVersion, events: batch });
      function sendWithFetch() {
        window.fetch(endpoint, { method: "POST", headers: { "Content-Type": "text/plain;charset=UTF-8" }, body: body, mode: "cors", keepalive: true }).then(function (response) {
          if (!response.ok && response.status >= 500) throw new Error("temporary_ingestion_error");
        }).catch(function () {
          var retryable = batch.filter(function (event) { return !event._localos_retried; });
          retryable.forEach(function (event) { event._localos_retried = true; });
          if (retryable.length) {
            queue = retryable.concat(queue).slice(0, maxQueueSize);
            if (!flushTimer) flushTimer = window.setTimeout(function () { flush(false); }, 5000);
          }
        });
      }
      try {
        if (useBeacon && navigator.sendBeacon) {
          if (!navigator.sendBeacon(endpoint, new Blob([body], { type: "text/plain;charset=UTF-8" }))) sendWithFetch();
        } else {
          sendWithFetch();
        }
      } catch (_error) {}
      if (queue.length) flushTimer = window.setTimeout(function () { flush(false); }, 1000);
    }

    function describeElement(element) {
      var href = element.href || element.getAttribute("href") || "";
      return {
        tag: (element.tagName || "").toLowerCase(),
        href: href,
        aria_label: element.getAttribute("aria-label") || "",
        text: (element.innerText || element.textContent || "").replace(/\s+/g, " ").trim().slice(0, 160)
      };
    }

    function trackPageView() {
      var nextPage = page();
      var nextPageKey = nextPage.hostname + nextPage.path;
      var now = Date.now();
      activePage = nextPage;
      if (nextPageKey === lastPageViewKey && now - lastPageViewAt < 1000) return;
      lastPageViewKey = nextPageKey;
      lastPageViewAt = now;
      pageDepths = {};
      enqueue("page_view", { page: activePage });
    }

    function checkpointForeground(eventName) {
      if (!consent || !foregroundStartedAt) return;
      var now = Date.now();
      var elapsed = Math.max(0, Math.min(30000, now - foregroundStartedAt));
      foregroundStartedAt = document.visibilityState === "visible" ? now : 0;
      if (elapsed >= 1000) enqueue(eventName || "heartbeat", { engagement_ms: elapsed, page: activePage });
    }

    function startHeartbeat() {
      if (heartbeatTimer || !consent) return;
      if (document.visibilityState === "visible") foregroundStartedAt = Date.now();
      heartbeatTimer = window.setInterval(function () { checkpointForeground("heartbeat"); }, 30000);
    }

    function stopHeartbeat() {
      if (heartbeatTimer) window.clearInterval(heartbeatTimer);
      heartbeatTimer = 0;
      foregroundStartedAt = 0;
    }

    document.addEventListener("click", function (event) {
      var target = event.target && event.target.closest ? event.target.closest("a,button,[role='button'],[data-localos-cta]") : null;
      if (!target) return;
      var element = describeElement(target);
      var outbound = false;
      if (element.href) {
        try {
          var url = new URL(element.href, window.location.href);
          outbound = url.protocol === "tel:" || url.protocol === "mailto:" || (url.hostname && url.hostname !== window.location.hostname);
        } catch (_error) {}
      }
      enqueue(outbound ? "outbound_click" : "click", { element: element });
      if (outbound) flush(false);
    }, true);

    document.addEventListener("focusin", function (event) {
      var form = event.target && event.target.closest ? event.target.closest("form") : null;
      if (!form || (startedForms && startedForms.has(form))) return;
      if (startedForms) startedForms.add(form);
      enqueue("form_start", { form: { id: form.id || "", name: form.getAttribute("name") || "", action: form.action || "" } });
    }, true);

    document.addEventListener("submit", function (event) {
      var form = event.target;
      enqueue("form_submit", { form: { id: form.id || "", name: form.getAttribute("name") || "", action: form.action || "" } });
      flush(false);
    }, true);

    window.addEventListener("scroll", function () {
      var height = Math.max(document.documentElement.scrollHeight, document.body ? document.body.scrollHeight : 0) - window.innerHeight;
      var depth = height <= 0 ? 100 : Math.min(100, Math.round((window.scrollY / height) * 100));
      [25, 50, 75, 100].forEach(function (mark) {
        if (depth >= mark && !pageDepths[mark]) {
          pageDepths[mark] = true;
          enqueue("scroll_depth", { depth: mark });
        }
      });
    }, { passive: true });

    function wrapHistory(method) {
      var original = window.history[method];
      if (!original) return;
      window.history[method] = function () {
        checkpointForeground("page_leave");
        var result = original.apply(this, arguments);
        window.setTimeout(trackPageView, 0);
        return result;
      };
    }

    wrapHistory("pushState");
    wrapHistory("replaceState");
    window.addEventListener("popstate", function () { checkpointForeground("page_leave"); trackPageView(); });
    window.addEventListener("pagehide", function () { checkpointForeground("page_leave"); flush(true); });
    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState === "hidden") {
        checkpointForeground("heartbeat");
        flush(true);
      } else if (consent) {
        foregroundStartedAt = Date.now();
      }
    });

    window.LocalOSTracker = {
      setConsent: function (allowed, options) {
        var wasAllowed = consent;
        consent = allowed === true;
        if (consent && !wasAllowed) {
          startHeartbeat();
          enqueue("session_start");
          if (!options || options.emitPageView !== false) trackPageView();
        } else if (!consent) {
          stopHeartbeat();
          queue = [];
          if (flushTimer) window.clearTimeout(flushTimer);
          flushTimer = 0;
        }
      },
      flush: function () { flush(false); }
    };

    startHeartbeat();
    enqueue("session_start");
    trackPageView();
  } catch (_fatalError) {}
})();
