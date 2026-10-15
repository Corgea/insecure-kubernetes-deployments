package com.example.catapp.orders;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Client for the orders service (insecure-api) on the cat app side.
 *
 * <p>Reads order status for the audit trail ({@link #audit(String)}) and reports fulfilment
 * events back to the orders service ({@link #publishShipped(String, String, String)}).
 */
@Service
public class OrderStatusConsumer {

    private static final Logger log = LoggerFactory.getLogger(OrderStatusConsumer.class);

    static final String EVENT_TOKEN_HEADER = "X-Orders-Event-Token";
    static final int MAX_TRACKED_ORDERS = 10_000;

    private static final Duration CONNECT_TIMEOUT = Duration.ofSeconds(2);
    private static final Duration READ_TIMEOUT = Duration.ofSeconds(5);

    private final RestTemplate restTemplate;
    private final String eventToken;
    private final Clock clock;
    private final Map<String, OrderAuditEntry> latest = new ConcurrentHashMap<>();

    @Autowired
    public OrderStatusConsumer(RestTemplateBuilder builder,
                               @Value("${orders.api.base-url}") String baseUrl,
                               @Value("${orders.api.event-token:}") String eventToken) {
        this(builder.rootUri(baseUrl)
                        .setConnectTimeout(CONNECT_TIMEOUT)
                        .setReadTimeout(READ_TIMEOUT)
                        .build(),
                eventToken,
                Clock.systemUTC());
    }

    OrderStatusConsumer(RestTemplate restTemplate, String eventToken, Clock clock) {
        this.restTemplate = restTemplate;
        this.eventToken = eventToken;
        this.clock = clock;
    }

    /**
     * Fetches the current status of an order and records it in the audit trail.
     */
    public OrderAuditEntry audit(String orderId) {
        OrderStatus status = restTemplate.getForObject("/orders/{id}/status", OrderStatus.class, orderId);
        if (status == null || status.getOrderStatus() == null) {
            throw new IllegalStateException("Orders service returned no status for order " + orderId);
        }

        Instant updatedAt = Instant.ofEpochMilli(status.getUpdatedAt());
        OrderAuditEntry entry = new OrderAuditEntry(orderId, status.getOrderStatus(), updatedAt, clock.instant());
        remember(entry);
        return entry;
    }

    /** Most recent audit observation of an order, if it has been audited since startup. */
    public Optional<OrderAuditEntry> lastAudit(String orderId) {
        return Optional.ofNullable(latest.get(orderId));
    }

    /**
     * Reports that an order's parcel has been handed to the carrier.
     */
    public void publishShipped(String orderId, String carrier, String trackingNumber) {
        publish(orderId, OrderStatusEvent.shipped(carrier, trackingNumber));
    }

    private void publish(String orderId, OrderStatusEvent event) {
        if (eventToken.isEmpty()) {
            throw new IllegalStateException("orders.api.event-token is not configured");
        }
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set(EVENT_TOKEN_HEADER, eventToken);

        restTemplate.postForEntity("/orders/{id}/events", new HttpEntity<>(event, headers), Void.class, orderId);
        log.info("Published {} event for order {}", event.getStatus(), orderId);
    }

    private void remember(OrderAuditEntry entry) {
        OrderAuditEntry previous = latest.get(entry.getOrderId());
        if (previous == null && latest.size() >= MAX_TRACKED_ORDERS) {
            // The audit log line below is the durable record; the map only serves lastAudit().
            log.debug("Audit cache full, not tracking order {}", entry.getOrderId());
        } else {
            latest.put(entry.getOrderId(), entry);
        }

        if (previous != null && !previous.getStatus().equals(entry.getStatus())) {
            log.info("Order {} moved from {} to {} (updated {})",
                    entry.getOrderId(), previous.getStatus(), entry.getStatus(), entry.getUpdatedAt());
        } else {
            log.info("Order {} is {} since {}", entry.getOrderId(), entry.getStatus(), entry.getUpdatedAt());
        }
    }
}
