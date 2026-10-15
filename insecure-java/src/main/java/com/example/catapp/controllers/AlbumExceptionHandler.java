package com.example.catapp.controllers;

import com.example.catapp.services.AlbumNotFoundException;
import com.example.catapp.services.AlbumValidationException;
import com.example.catapp.services.ShareLinkUnavailableException;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ControllerAdvice;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseBody;
import org.springframework.web.bind.annotation.ResponseStatus;

/**
 * Error responses for the album and share-link endpoints. Ordered ahead of the app-wide
 * {@link com.example.catapp.config.GlobalExceptionHandler}, whose catch-all would otherwise turn
 * these into 500s.
 */
@ControllerAdvice(assignableTypes = {AlbumController.class, ShareLinkController.class})
@Order(Ordered.HIGHEST_PRECEDENCE)
public class AlbumExceptionHandler {

    @ExceptionHandler({AlbumNotFoundException.class, ShareLinkUnavailableException.class})
    @ResponseStatus(HttpStatus.NOT_FOUND)
    @ResponseBody
    public String notFound(RuntimeException e) {
        return e.getMessage();
    }

    @ExceptionHandler(AlbumValidationException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    @ResponseBody
    public String invalidRequest(AlbumValidationException e) {
        return e.getMessage();
    }
}
