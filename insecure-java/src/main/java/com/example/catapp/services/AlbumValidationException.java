package com.example.catapp.services;

/**
 * Thrown when an album request is well-formed but not allowed, such as a blank name. The message
 * is shown to the user.
 */
public class AlbumValidationException extends RuntimeException {

    public AlbumValidationException(String message) {
        super(message);
    }
}
