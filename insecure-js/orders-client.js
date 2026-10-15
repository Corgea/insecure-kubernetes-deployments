/**
 * Browser client for the orders service (insecure-api, /orders routes).
 *
 * Loaded with a plain <script> tag on the storefront, where it is exposed as
 * `window.OrdersClient`, and required from Node for scripted checks.
 *
 *   OrdersClient.configure({ baseUrl: 'https://orders.example.com' });
 *   const order = await OrdersClient.createOrder({ items: [{ sku: 'CAT-01', quantity: 1 }] });
 *   OrdersClient.mountTracker(document.querySelector('#order-tracker'));
 */
(function (root, factory) {
  const client = factory();
  if (typeof module === 'object' && module.exports) {
    module.exports = client;
  } else {
    root.OrdersClient = client;
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const REQUEST_TIMEOUT_MS = 5000;
  const CREATE_MAX_ATTEMPTS = 3;
  const RETRY_BASE_DELAY_MS = 300;
  const POLL_INTERVAL_MS = 5000;
  const MAX_POLLS = 120;

  const STATUS_LABELS = new Map([
    ['placed', 'Order placed'],
    ['shipped', 'Shipped'],
    ['delivered', 'Delivered'],
    ['cancelled', 'Cancelled'],
    ['unknown', 'Status unavailable'],
  ]);
  const FINAL_STATUSES = new Set(['delivered', 'cancelled']);

  let baseUrl = '';

  class OrdersApiError extends Error {
    constructor(message, { status = 0, code = 'http' } = {}) {
      super(message);
      this.name = 'OrdersApiError';
      this.status = status;
      this.code = code;
    }
  }

  function configure(options = {}) {
    if (typeof options.baseUrl === 'string') {
      baseUrl = options.baseUrl.replace(/\/+$/, '');
    }
  }

  function delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  async function requestJson(path, { method = 'GET', body, timeoutMs = REQUEST_TIMEOUT_MS } = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const headers = { Accept: 'application/json' };
    if (body !== undefined) {
      headers['Content-Type'] = 'application/json';
    }

    try {
      const response = await fetch(baseUrl + path, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
        credentials: 'omit',
        signal: controller.signal,
      });
      if (!response.ok) {
        const problem = await response.json().catch(() => null);
        const detail = problem && typeof problem.detail === 'string' ? problem.detail : response.statusText;
        throw new OrdersApiError(`${method} ${path} failed: ${detail}`, { status: response.status });
      }
      return await response.json();
    } catch (err) {
      if (err instanceof OrdersApiError) {
        throw err;
      }
      if (err && err.name === 'AbortError') {
        throw new OrdersApiError(`${method} ${path} timed out after ${timeoutMs} ms`, { code: 'timeout' });
      }
      throw new OrdersApiError(`${method} ${path} failed: ${err && err.message}`, { code: 'network' });
    } finally {
      clearTimeout(timer);
    }
  }

  /**
   * Places an order and resolves with the created order as the API returns it.
   *
   * Checkout should not fail because the API was briefly slow, so timeouts are
   * retried with exponential backoff. HTTP error responses (validation errors,
   * a full order store) are not retried and reject straight away.
   */
  async function createOrder(payload) {
    let lastError;
    for (let attempt = 1; attempt <= CREATE_MAX_ATTEMPTS; attempt += 1) {
      try {
        return await requestJson('/orders', { method: 'POST', body: payload });
      } catch (err) {
        lastError = err;
        if (err.code !== 'timeout' || attempt === CREATE_MAX_ATTEMPTS) {
          throw err;
        }
        await delay(RETRY_BASE_DELAY_MS * 2 ** (attempt - 1));
      }
    }
    throw lastError;
  }

  function normalizeStatus(value) {
    if (typeof value !== 'string') {
      return 'unknown';
    }
    const status = value.trim().toLowerCase();
    return STATUS_LABELS.has(status) ? status : 'unknown';
  }

  /** Resolves with `{ id, status }`, where status is one of the STATUS_LABELS keys. */
  async function fetchOrderStatus(id) {
    const data = await requestJson(`/orders/${encodeURIComponent(id)}/status`);
    return { id, status: normalizeStatus(data.orderStatus) };
  }

  function renderOrderStatus(element, order) {
    const status = order ? normalizeStatus(order.status) : 'unknown';
    element.textContent = STATUS_LABELS.get(status);
    element.dataset.status = status;
    element.classList.toggle('order-status--final', FINAL_STATUSES.has(status));
  }

  /**
   * Polls an order's status into `element` until it reaches a final status or
   * `maxPolls` requests have been made. Returns a function that stops polling.
   */
  function watchOrderStatus(id, element, { intervalMs = POLL_INTERVAL_MS, maxPolls = MAX_POLLS, onError } = {}) {
    let polls = 0;
    let timer = null;
    let stopped = false;

    async function poll() {
      polls += 1;
      try {
        const order = await fetchOrderStatus(id);
        if (stopped) {
          return;
        }
        renderOrderStatus(element, order);
        if (FINAL_STATUSES.has(order.status)) {
          return;
        }
      } catch (err) {
        if (stopped) {
          return;
        }
        if (typeof onError === 'function') {
          onError(err);
        }
      }
      if (polls < maxPolls) {
        timer = setTimeout(poll, intervalMs);
      }
    }

    poll();
    return function stop() {
      stopped = true;
      clearTimeout(timer);
    };
  }

  /**
   * Wires a tracker widget: a form with an `orderId` input and an element
   * marked `[data-order-status]` that shows the status.
   */
  function mountTracker(container) {
    const form = container.querySelector('form');
    const output = container.querySelector('[data-order-status]');
    let stop = null;

    form.addEventListener('submit', (event) => {
      event.preventDefault();
      const id = form.elements.orderId.value.trim();
      if (stop) {
        stop();
        stop = null;
      }
      if (!id) {
        output.textContent = '';
        return;
      }
      stop = watchOrderStatus(id, output, {
        onError: (err) => {
          output.dataset.status = 'error';
          if (err.status === 404) {
            output.textContent = 'We could not find that order.';
            stop();
            return;
          }
          output.textContent = 'Could not load the order status.';
        },
      });
    });

    return function unmount() {
      if (stop) {
        stop();
      }
    };
  }

  return {
    configure,
    createOrder,
    fetchOrderStatus,
    renderOrderStatus,
    watchOrderStatus,
    mountTracker,
    OrdersApiError,
  };
});
