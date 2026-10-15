package com.example.catapp.services;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Per-album view and download counters for album owners, plus an audit log line for every access.
 * Counters live in memory and start from zero when the app restarts; the audit log is the durable
 * record.
 */
@Component
public class AccessStats {

    private static final Logger AUDIT = LoggerFactory.getLogger("com.example.catapp.audit");

    public enum AccessType {
        VIEW,
        DOWNLOAD
    }

    private final ConcurrentMap<Integer, Counters> counters = new ConcurrentHashMap<>();

    /**
     * Records one access to an album. {@code userId} is null for anonymous visitors.
     */
    public void recordAccess(int albumId, AccessType type, Integer userId) {
        Counters stats = counters.computeIfAbsent(albumId, id -> new Counters());
        Instant now = Instant.now();
        switch (type) {
            case VIEW:
                stats.incrementViews();
                stats.lastViewedAt = now;
                break;
            case DOWNLOAD:
                stats.incrementViews();
                stats.lastDownloadedAt = now;
                break;
            default:
                throw new IllegalArgumentException("Unsupported access type " + type);
        }
        AUDIT.info("album={} access={} user={}", albumId, type, userId == null ? "anonymous" : userId);
    }

    public Snapshot snapshot(int albumId) {
        Counters stats = counters.get(albumId);
        if (stats == null) {
            return new Snapshot(0, 0, null, null);
        }
        return new Snapshot(stats.views.get(), stats.downloads.get(), stats.lastViewedAt, stats.lastDownloadedAt);
    }

    /** Drops the counters of a deleted album. */
    public void forget(int albumId) {
        counters.remove(albumId);
    }

    private static final class Counters {
        private final AtomicLong views = new AtomicLong();
        private final AtomicLong downloads = new AtomicLong();
        private volatile Instant lastViewedAt;
        private volatile Instant lastDownloadedAt;

        void incrementViews() {
            views.incrementAndGet();
        }

        void incrementDownloads() {
            downloads.incrementAndGet();
        }
    }

    /**
     * Point-in-time copy of an album's counters, safe to hand to the JSON layer.
     */
    public static final class Snapshot {
        private final long views;
        private final long downloads;
        private final Instant lastViewedAt;
        private final Instant lastDownloadedAt;

        Snapshot(long views, long downloads, Instant lastViewedAt, Instant lastDownloadedAt) {
            this.views = views;
            this.downloads = downloads;
            this.lastViewedAt = lastViewedAt;
            this.lastDownloadedAt = lastDownloadedAt;
        }

        public long getViews() {
            return views;
        }

        public long getDownloads() {
            return downloads;
        }

        public Instant getLastViewedAt() {
            return lastViewedAt;
        }

        public Instant getLastDownloadedAt() {
            return lastDownloadedAt;
        }
    }
}
