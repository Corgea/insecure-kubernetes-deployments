package com.example.catapp.services;

import com.example.catapp.dto.CommentView;
import com.example.catapp.models.Comment;
import com.example.catapp.repositories.CommentRepository;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.stream.Collectors;

@Service
public class DefaultCommentService implements CommentService {

    private final CommentRepository commentRepository;

    public DefaultCommentService(CommentRepository commentRepository) {
        this.commentRepository = commentRepository;
    }

    @Override
    public List<CommentView> listAll() {
        return commentRepository.findAll().stream()
                .map(CommentView::from)
                .collect(Collectors.toList());
    }

    @Override
    public CommentView add(String text) {
        String trimmed = text == null ? "" : text.trim();
        if (trimmed.isEmpty()) {
            throw new IllegalArgumentException("Comment text must not be blank");
        }
        Comment comment = new Comment();
        comment.setText(trimmed);
        return CommentView.from(commentRepository.save(comment));
    }
}
