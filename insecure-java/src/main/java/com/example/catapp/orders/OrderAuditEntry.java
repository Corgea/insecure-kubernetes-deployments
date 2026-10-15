package com.example.catapp.orders;

import java.time.Duration;
import java.time.Instant;

/**
 * One observation of an order's status, kept by {@link OrderStatusConsumer} for the audit trail.
 */
public final class OrderAuditEntry {

    private final String orderId;
    private final String status;
    private final Instant updatedAt;
    private final Instant observedAt;

    public OrderAuditEntry(String orderId, String status, Instant updatedAt, Instant observedAt) {
        this.orderId = orderId;
        this.status = status;
        this.updatedAt = updatedAt;
        this.observedAt = observedAt;
    }

    public String getOrderId() {
        return orderId;
    }

    public String getStatus() {
        return status;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }

    public Instant getObservedAt() {
        return observedAt;
    }

    /** How long the order has been in its current status when it was observed. */
    public long getSecondsInStatus() {
        return Duration.between(updatedAt, observedAt).getSeconds();
    }
}
