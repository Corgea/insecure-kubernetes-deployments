package com.example.catapp.models;

import javax.persistence.Column;
import javax.persistence.Entity;
import javax.persistence.GeneratedValue;
import javax.persistence.GenerationType;
import javax.persistence.Id;
import javax.persistence.Table;
import java.time.Instant;

/**
 * A link that opens one album for anyone holding its token, whatever the album's visibility.
 */
@Entity
@Table(name = "share_links")
public class ShareLink {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    @Column(nullable = false, unique = true, length = 64)
    private String token;

    @Column(nullable = false)
    private Integer albumId;

    @Column(nullable = false, updatable = false)
    private Integer createdBy;

    @Column(nullable = false, updatable = false)
    private Instant createdAt;

    @Column(nullable = false)
    private Instant expiresAt;

    /** One-time links stop working after the first successful open. */
    private boolean oneTime;

    private boolean used;

    private Instant usedAt;

    public boolean isExpired(Instant now) {
        return !now.isBefore(expiresAt);
    }

    public boolean isActive(Instant now) {
        return !isExpired(now) && !(oneTime && used);
    }

    public Integer getId() {
        return id;
    }

    public void setId(Integer id) {
        this.id = id;
    }

    public String getToken() {
        return token;
    }

    public void setToken(String token) {
        this.token = token;
    }

    public Integer getAlbumId() {
        return albumId;
    }

    public void setAlbumId(Integer albumId) {
        this.albumId = albumId;
    }

    public Integer getCreatedBy() {
        return createdBy;
    }

    public void setCreatedBy(Integer createdBy) {
        this.createdBy = createdBy;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(Instant createdAt) {
        this.createdAt = createdAt;
    }

    public Instant getExpiresAt() {
        return expiresAt;
    }

    public void setExpiresAt(Instant expiresAt) {
        this.expiresAt = expiresAt;
    }

    public boolean isOneTime() {
        return oneTime;
    }

    public void setOneTime(boolean oneTime) {
        this.oneTime = oneTime;
    }

    public boolean isUsed() {
        return used;
    }

    public void setUsed(boolean used) {
        this.used = used;
    }

    public Instant getUsedAt() {
        return usedAt;
    }

    public void setUsedAt(Instant usedAt) {
        this.usedAt = usedAt;
    }
}
