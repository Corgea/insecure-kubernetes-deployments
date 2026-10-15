package com.example.catapp.orders;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Body of {@code POST /orders/{id}/events}: a fulfilment event reported to the orders service.
 */
public final class OrderStatusEvent {

    static final String SOURCE = "catapp-audit";

    private final String status;
    private final String carrier;
    private final String trackingNumber;

    private OrderStatusEvent(String status, String carrier, String trackingNumber) {
        this.status = status;
        this.carrier = carrier;
        this.trackingNumber = trackingNumber;
    }

    /** The parcel has been handed to the carrier. */
    public static OrderStatusEvent shipped(String carrier, String trackingNumber) {
        return new OrderStatusEvent("SHIPPED", carrier, trackingNumber);
    }

    public String getStatus() {
        return status;
    }

    public String getCarrier() {
        return carrier;
    }

    @JsonProperty("tracking_number")
    public String getTrackingNumber() {
        return trackingNumber;
    }

    public String getSource() {
        return SOURCE;
    }
}
