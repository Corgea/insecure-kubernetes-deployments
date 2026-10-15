package com.example.catapp.services;

/**
 * Thrown when a share link cannot be used: malformed, revoked, expired or already used. The
 * message is shown to the visitor, so it never says which of these applies.
 */
public class ShareLinkUnavailableException extends RuntimeException {

    public ShareLinkUnavailableException() {
        super("This share link is not available");
    }
}
