package com.example.catapp.services;

import com.example.catapp.dto.CommentView;

import java.util.List;

public interface CommentService {

    List<CommentView> listAll();

    /**
     * Saves a new comment with surrounding whitespace removed.
     *
     * @throws IllegalArgumentException if {@code text} is null or blank
     */
    CommentView add(String text);
}
