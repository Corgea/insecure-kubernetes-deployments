package com.example.catapp.controllers;

/**
 * Names of the attributes the app keeps in the HTTP session.
 */
public final class SessionKeys {

    /** Id of the logged-in user, as an {@link Integer}. Absent for anonymous visitors. */
    public static final String USER_ID = "userId";

    private SessionKeys() {
    }
}
