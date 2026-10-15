package com.example.catapp.controllers;

import com.example.catapp.dto.CommentView;
import com.example.catapp.repositories.CommentRepository;
import com.example.catapp.services.CommentService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.support.RedirectAttributes;

import java.util.List;

@Controller
public class CommentController {

    @Autowired
    private CommentService commentService;

    @Autowired
    private CommentRepository commentRepository;

    @GetMapping("/addComment")
    public String addCommentForm() {
        return "addComment"; // Returns addComment.html
    }

    @PostMapping("/addComment")
    public String addComment(@RequestParam String commentText, Model model) {
        try {
            commentService.add(commentText);
            model.addAttribute("message", "Comment added");
        } catch (IllegalArgumentException e) {
            model.addAttribute("message", e.getMessage());
        }
        return "addCommentResult"; // Returns addCommentResult.html
    }

    @GetMapping("/comments")
    public String getComments(Model model) {
        List<CommentView> comments = commentService.listAll();
        model.addAttribute("comments", comments);
        return "comments"; // Returns comments.html
    }

        // Vulnerable Endpoint: Delete Comment without CSRF Protection
    @PostMapping("/deleteComment")
    public String deleteComment(@RequestParam int commentId, RedirectAttributes redirectAttributes) {
        commentRepository.deleteById(commentId);
        redirectAttributes.addFlashAttribute("message", "Comment deleted");
        return "redirect:/comments";
    }
}
