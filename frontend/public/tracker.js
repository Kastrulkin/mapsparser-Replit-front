(function () {
  "use strict";

  try {
    var script = document.currentScript;
    if (!script) return;
    var trackerId = script.getAttribute("data-business") || "";
    if (trackerId.indexOf("pub_") !== 0) return;
    var trackerVersion = "1.4.0";
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
    var sectionObserver = null;
    var observedSections = [];
    var ctaObserver = null;
    var observedCtas = [];
    var startedForms = typeof WeakSet === "function" ? new WeakSet() : null;

    function canonicalHostname(value) {
      var hostname = String(value || "").toLowerCase().replace(/\.$/, "");
      return hostname.indexOf("www.") === 0 ? hostname.slice(4) : hostname;
    }

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

    function pageKey(value) {
      return canonicalHostname(value.hostname) + value.path;
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

    function formDescriptor(form) {
      var section = form && form.closest ? form.closest("[data-localos-section],section,.t-rec") : null;
      return {
        id: form && (form.getAttribute("data-localos-form") || form.id) || "",
        name: form && form.getAttribute("name") || "",
        action: form && form.action || "",
        section_key: section ? (section.getAttribute("data-localos-section") || section.id || "").slice(0, 100) : ""
      };
    }

    function ctaDescriptor(element) {
      var section = element && element.closest ? element.closest("[data-localos-section],section,.t-rec") : null;
      var sectionKey = section ? (section.getAttribute("data-localos-section") || section.id || "") : "";
      return {
        id: element.getAttribute("data-localos-cta") || "",
        label: element.getAttribute("data-localos-cta-label") || element.getAttribute("aria-label") || (element.innerText || element.textContent || "").replace(/\s+/g, " ").trim().slice(0, 160),
        position: element.getAttribute("data-localos-cta-position") || "cta-" + (Array.prototype.indexOf.call(document.querySelectorAll("[data-localos-cta]"), element) + 1),
        section_key: sectionKey.slice(0, 100)
      };
    }

    function trackPageView() {
      var nextPage = page();
      var nextPageKey = pageKey(nextPage);
      activePage = nextPage;
      if (nextPageKey === lastPageViewKey) {
        if (!sectionObserver) setupSectionTracking();
        if (!ctaObserver) setupCtaTracking();
        return;
      }
      lastPageViewKey = nextPageKey;
      pageDepths = {};
      enqueue("page_view", { page: activePage });
      setupSectionTracking();
      setupCtaTracking();
    }

    function normalizedSectionLabel(value) {
      return String(value || "").replace(/\s+/g, " ").trim().slice(0, 120);
    }

    function linkedSectionLabel(element) {
      if (!element.id) return "";
      var links = Array.prototype.slice.call(document.querySelectorAll("a[href]"));
      var match = links.find(function (link) {
        try { return new URL(link.getAttribute("href"), window.location.href).hash === "#" + element.id; }
        catch (_error) { return false; }
      });
      return match ? normalizedSectionLabel(match.innerText || match.textContent) : "";
    }

    function contentSectionLabel(element) {
      var candidates = Array.prototype.slice.call(element.querySelectorAll(".t-title,.t-name,.t-heading,[data-elem-type='text'] .tn-atom,.t-text,.t-descr"));
      for (var index = 0; index < candidates.length; index += 1) {
        var value = normalizedSectionLabel(candidates[index].innerText || candidates[index].textContent);
        if (value.length >= 3) return value;
      }
      return "";
    }

    function sectionDescriptor(element, position) {
      var heading = element.querySelector("h1,h2,h3,[role='heading'],.t-title,.t-name,.t-heading");
      var label = element.getAttribute("data-localos-section-label") || element.getAttribute("data-localos-section") || element.getAttribute("aria-label") || linkedSectionLabel(element) || (heading ? heading.textContent : "") || contentSectionLabel(element) || "Секция " + position;
      label = normalizedSectionLabel(label);
      var key = element.getAttribute("data-localos-section") || element.id || label.toLowerCase().replace(/[^a-zа-яё0-9]+/gi, "-").replace(/^-|-$/g, "").slice(0, 100) || "section-" + position;
      return { element: element, key: key, label: label, position: position, visibleAt: 0, viewed: false, timer: 0 };
    }

    function leaveSection(state) {
      if (state.timer) window.clearTimeout(state.timer);
      state.timer = 0;
      if (!state.visibleAt || !state.viewed) {
        state.visibleAt = 0;
        return;
      }
      var elapsed = Math.max(0, Math.min(600000, Date.now() - state.visibleAt));
      state.visibleAt = 0;
      if (elapsed >= 1000) enqueue("section_engagement", { engagement_ms: elapsed, section: { key: state.key, label: state.label, position: state.position }, page: activePage });
    }

    function stopSectionTracking() {
      observedSections.forEach(leaveSection);
      observedSections = [];
      if (sectionObserver) sectionObserver.disconnect();
      sectionObserver = null;
    }

    function stopCtaTracking() {
      observedCtas.forEach(function (state) { if (state.timer) window.clearTimeout(state.timer); });
      observedCtas = [];
      if (ctaObserver) ctaObserver.disconnect();
      ctaObserver = null;
    }

    function setupCtaTracking() {
      stopCtaTracking();
      if (!consent || typeof window.IntersectionObserver !== "function") return;
      var elements = Array.prototype.slice.call(document.querySelectorAll("[data-localos-cta]"));
      observedCtas = elements.map(function (element) { return { element: element, seen: false, timer: 0 }; });
      ctaObserver = new window.IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          var state = observedCtas.find(function (item) { return item.element === entry.target; });
          if (!state || state.seen) return;
          if (entry.isIntersecting && entry.intersectionRatio >= 0.5) {
            if (!state.timer) state.timer = window.setTimeout(function () {
              state.timer = 0;
              if (state.seen) return;
              state.seen = true;
              enqueue("cta_impression", { cta: ctaDescriptor(state.element), page: activePage });
              ctaObserver.unobserve(state.element);
            }, 500);
          } else if (state.timer) {
            window.clearTimeout(state.timer);
            state.timer = 0;
          }
        });
      }, { threshold: [0, 0.5, 1] });
      observedCtas.forEach(function (state) { ctaObserver.observe(state.element); });
    }

    function setupSectionTracking() {
      stopSectionTracking();
      if (!consent || typeof window.IntersectionObserver !== "function") return;
      var elements = Array.prototype.slice.call(document.querySelectorAll("[data-localos-section], main section, body > section, .t-records > .t-rec"));
      elements = elements.filter(function (element, index) { return elements.indexOf(element) === index; });
      observedSections = elements.map(function (element, index) { return sectionDescriptor(element, index + 1); });
      sectionObserver = new window.IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          var state = observedSections.find(function (item) { return item.element === entry.target; });
          if (!state) return;
          var sectionHeight = Math.max(1, Number(entry.boundingClientRect && entry.boundingClientRect.height) || 0);
          var viewportHeight = Math.max(1, Number(entry.rootBounds && entry.rootBounds.height) || document.documentElement.clientHeight || window.innerHeight || 0);
          var visibleHeight = Math.max(0, Number(entry.intersectionRect && entry.intersectionRect.height) || 0);
          var enoughVisible = visibleHeight >= Math.min(sectionHeight, viewportHeight) * 0.5;
          if (entry.isIntersecting && enoughVisible) {
            if (!state.visibleAt) state.visibleAt = Date.now();
            if (!state.viewed && !state.timer) {
              state.timer = window.setTimeout(function () {
                state.timer = 0;
                if (!state.visibleAt || state.viewed) return;
                state.viewed = true;
                enqueue("section_view", { section: { key: state.key, label: state.label, position: state.position }, page: activePage });
              }, 1000);
            }
          } else {
            leaveSection(state);
          }
        });
      }, { threshold: [0, 0.1, 0.2, 0.3, 0.4, 0.5] });
      observedSections.forEach(function (state) { sectionObserver.observe(state.element); });
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
      var explicitCta = target.closest ? target.closest("[data-localos-cta]") : null;
      var outbound = false;
      if (element.href) {
        try {
          var url = new URL(element.href, window.location.href);
          outbound = url.protocol === "tel:" || url.protocol === "mailto:" || (url.hostname && canonicalHostname(url.hostname) !== canonicalHostname(window.location.hostname));
        } catch (_error) {}
      }
      if (explicitCta) enqueue("cta_click", { element: element, cta: ctaDescriptor(explicitCta) });
      enqueue(outbound ? "outbound_click" : "click", { element: element });
      if (outbound) flush(false);
    }, true);

    document.addEventListener("focusin", function (event) {
      var form = event.target && event.target.closest ? event.target.closest("form") : null;
      if (!form || (startedForms && startedForms.has(form))) return;
      if (startedForms) startedForms.add(form);
      enqueue("form_start", { form: formDescriptor(form) });
    }, true);

    document.addEventListener("submit", function (event) {
      var form = event.target;
      enqueue("form_submit_attempt", { form: formDescriptor(form) });
      flush(false);
    }, true);

    document.addEventListener("invalid", function (event) {
      var form = event.target && event.target.closest ? event.target.closest("form") : null;
      if (!form) return;
      enqueue("form_validation_error", { form: formDescriptor(form), error_type: "browser_validation" });
    }, true);

    function trackTildaSuccess(event) {
      var form = event.target && event.target.closest ? event.target.closest("form") : null;
      enqueue("form_submit_success", { form: formDescriptor(form) });
      flush(false);
    }
    document.addEventListener("tildaform:aftersuccess", trackTildaSuccess);

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
        var previousPageKey = pageKey(page());
        var result = original.apply(this, arguments);
        if (pageKey(page()) !== previousPageKey) {
          checkpointForeground("page_leave");
          stopSectionTracking();
          stopCtaTracking();
          window.setTimeout(trackPageView, 0);
        }
        return result;
      };
    }

    wrapHistory("pushState");
    wrapHistory("replaceState");
    window.addEventListener("popstate", function () {
      if (pageKey(page()) === lastPageViewKey) return;
      checkpointForeground("page_leave");
      stopSectionTracking();
      stopCtaTracking();
      trackPageView();
    });
    window.addEventListener("pagehide", function () { stopSectionTracking(); stopCtaTracking(); checkpointForeground("page_leave"); flush(true); });
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
          else { setupSectionTracking(); setupCtaTracking(); }
        } else if (!consent) {
          stopSectionTracking();
          stopCtaTracking();
          stopHeartbeat();
          queue = [];
          lastPageViewKey = "";
          if (flushTimer) window.clearTimeout(flushTimer);
          flushTimer = 0;
        }
      },
      trackFormResult: function (result, form, errorType) {
        var allowed = {
          validation_error: "form_validation_error",
          success: "form_submit_success",
          error: "form_submit_error"
        };
        var eventName = allowed[result];
        if (!eventName) return false;
        enqueue(eventName, { form: formDescriptor(form), error_type: String(errorType || "").slice(0, 80) });
        flush(false);
        return true;
      },
      getAttribution: function () {
        return consent ? { tracker_id: trackerId, session_id: sessionId } : { tracker_id: trackerId, session_id: "" };
      },
      flush: function () { flush(false); }
    };

    startHeartbeat();
    enqueue("session_start");
    trackPageView();
  } catch (_fatalError) {}
})();
