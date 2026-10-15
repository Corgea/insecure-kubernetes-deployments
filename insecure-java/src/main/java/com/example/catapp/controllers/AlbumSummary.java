package com.example.catapp.controllers;

import com.example.catapp.models.Album;
import com.example.catapp.models.Album.Visibility;

import java.time.Instant;

/**
 * JSON view of an album for the album list endpoints.
 */
public class AlbumSummary {

    private final int id;
    private final String name;
    private final Visibility visibility;
    private final int pictureCount;
    private final Instant createdAt;

    public AlbumSummary(Album album, int pictureCount) {
        this.id = album.getId();
        this.name = album.getName();
        this.visibility = album.getVisibility();
        this.pictureCount = pictureCount;
        this.createdAt = album.getCreatedAt();
    }

    public int getId() {
        return id;
    }

    public String getName() {
        return name;
    }

    public Visibility getVisibility() {
        return visibility;
    }

    public int getPictureCount() {
        return pictureCount;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}
