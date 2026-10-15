package com.example.catapp.services;

/**
 * Thrown when an album does not exist or the current user may not see it. Both cases look the
 * same to the caller so that album ids cannot be probed.
 */
public class AlbumNotFoundException extends RuntimeException {

    public AlbumNotFoundException(int albumId) {
        super("Album " + albumId + " not found");
    }
}
