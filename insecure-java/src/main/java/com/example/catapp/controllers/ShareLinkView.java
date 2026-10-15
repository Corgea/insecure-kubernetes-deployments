package com.example.catapp.controllers;

import com.example.catapp.models.ShareLink;

import java.time.Instant;

/**
 * JSON view of a share link for the album owner.
 */
public class ShareLinkView {

    private final int id;
    private final String url;
    private final Instant expiresAt;
    private final boolean oneTime;

    public ShareLinkView(ShareLink link) {
        this.id = link.getId();
        this.url = "/shared/" + link.getToken();
        this.expiresAt = link.getExpiresAt();
        this.oneTime = link.isOneTime();
    }

    public int getId() {
        return id;
    }

    public String getUrl() {
        return url;
    }

    public Instant getExpiresAt() {
        return expiresAt;
    }

    public boolean isOneTime() {
        return oneTime;
    }
}
