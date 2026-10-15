package com.example.catapp.dto;

import com.example.catapp.models.Comment;

/**
 * Read-only view of a comment, handed to controllers and templates instead of the entity.
 */
public final class CommentView {

    private final int id;
    private final String text;

    public CommentView(int id, String text) {
        this.id = id;
        this.text = text;
    }

    public static CommentView from(Comment comment) {
        return new CommentView(comment.getId(), comment.getText());
    }

    public int getId() {
        return id;
    }

    public String getText() {
        return text;
    }
}
