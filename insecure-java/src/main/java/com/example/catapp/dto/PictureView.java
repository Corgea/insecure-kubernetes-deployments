package com.example.catapp.dto;

import com.example.catapp.models.CatPicture;

/**
 * Read-only view of a cat picture, handed to controllers and templates instead of the entity.
 */
public final class PictureView {

    private final int id;
    private final String name;
    private final String url;
    private final int ownerId;

    public PictureView(int id, String name, String url, int ownerId) {
        this.id = id;
        this.name = name;
        this.url = url;
        this.ownerId = ownerId;
    }

    public static PictureView from(CatPicture picture) {
        return new PictureView(picture.getId(), picture.getName(), picture.getUrl(), picture.getOwnerId());
    }

    public int getId() {
        return id;
    }

    public String getName() {
        return name;
    }

    public String getUrl() {
        return url;
    }

    public int getOwnerId() {
        return ownerId;
    }
}
