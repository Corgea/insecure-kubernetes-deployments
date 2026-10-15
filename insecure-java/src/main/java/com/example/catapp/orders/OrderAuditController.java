package com.example.catapp.orders;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestClientException;

import java.util.regex.Pattern;

/**
 * Audit view of an order: what the orders service reports and when its status last changed.
 */
@RestController
@RequestMapping("/orders")
public class OrderAuditController {

    private static final Logger log = LoggerFactory.getLogger(OrderAuditController.class);

    // Order ids are uuid4 hex strings minted by the orders service.
    private static final Pattern ORDER_ID = Pattern.compile("[0-9a-f]{32}");

    private final OrderStatusConsumer consumer;

    public OrderAuditController(OrderStatusConsumer consumer) {
        this.consumer = consumer;
    }

    @GetMapping("/{orderId}/audit")
    public ResponseEntity<OrderAuditEntry> audit(@PathVariable String orderId) {
        if (!ORDER_ID.matcher(orderId).matches()) {
            return ResponseEntity.badRequest().build();
        }
        try {
            return ResponseEntity.ok(consumer.audit(orderId));
        } catch (HttpClientErrorException.NotFound e) {
            return ResponseEntity.notFound().build();
        } catch (RestClientException e) {
            log.warn("Orders service call failed for order {}", orderId, e);
            return ResponseEntity.status(HttpStatus.BAD_GATEWAY).build();
        }
    }
}
