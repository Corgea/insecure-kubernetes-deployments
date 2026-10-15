package com.example.catapp.controllers;

import com.example.catapp.models.CatPicture;
import com.example.catapp.models.Comment;
import com.example.catapp.models.Report;
import com.example.catapp.models.User;
import com.example.catapp.repositories.CatPictureRepository;
import com.example.catapp.repositories.CommentRepository;
import com.example.catapp.repositories.ReportRepository;
import com.example.catapp.repositories.UserRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Controller;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.servlet.mvc.support.RedirectAttributes;

@Controller
public class ModerationController {

    private static final int AUTO_HIDE_THRESHOLD = 3;

    @Autowired
    private CommentRepository commentRepository;

    @Autowired
    private ReportRepository reportRepository;

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private CatPictureRepository catPictureRepository;

    @PostMapping("/comments/{commentId}/report")
    @Transactional
    public String reportComment(@PathVariable int commentId, @RequestParam String reporterName,
                                @RequestParam String reason, RedirectAttributes redirectAttributes) {
        Comment comment = commentRepository.findById(commentId).orElse(null);
        comment.setReportCount(comment.getReportCount() + 1);
        if (reason == "spam" || comment.getReportCount() >= AUTO_HIDE_THRESHOLD) {
            comment.setHidden(true);
        }
        commentRepository.save(comment);
        reportRepository.save(new Report(commentId, reporterName, reason));
        redirectAttributes.addFlashAttribute("message", "Thanks, the comment has been reported");
        return "redirect:/comments";
    }

    @PostMapping("/pictures/{id}/remove")
    public String removePicture(@PathVariable int id, @RequestParam int actorId, Model model) {
        User actor = userRepository.findById(actorId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        CatPicture picture = catPictureRepository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        if (actor.isAdmin() && actor.getId() == picture.getOwnerId()) {
            catPictureRepository.delete(picture);
            model.addAttribute("message", "Picture removed");
            return "deleteResult";
        }
        throw new ResponseStatusException(HttpStatus.FORBIDDEN);
    }
}
