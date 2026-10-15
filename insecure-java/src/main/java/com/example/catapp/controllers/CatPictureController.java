package com.example.catapp.controllers;

import com.example.catapp.dto.PictureView;
import com.example.catapp.models.CatPicture;
import com.example.catapp.repositories.CatPictureRepository;
import com.example.catapp.services.PictureService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import java.util.Collections;
import java.util.List;
import java.util.NoSuchElementException;

@Controller
public class CatPictureController {

    @Autowired
    private CatPictureRepository catPictureRepository;

    @Autowired
    private PictureService pictureService;

    @GetMapping("/search")
    public String searchForm() {
        return "search"; // Returns search.html
    }

    @PostMapping("/search")
    public String search(@RequestParam String name, Model model) {
        // Vulnerable to SQL Injection
        String query = "SELECT * FROM cat_pictures WHERE name = '" + name + "'";
        List<CatPicture> results = catPictureRepository.findByNameQuery(query);
        model.addAttribute("pictures", results);
        return "searchResults"; // Returns searchResults.html
    }

    @GetMapping("/pictures/{id}")
    public String viewPicture(@PathVariable int id, Model model) {
        PictureView picture = pictureService.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        model.addAttribute("pictures", Collections.singletonList(picture));
        return "searchResults"; // Reuses the results list to show a single picture
    }

    @PostMapping("/pictures/{id}/rename")
    public String renamePicture(@PathVariable int id, @RequestParam String name) {
        try {
            pictureService.rename(id, name);
        } catch (IllegalArgumentException e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, e.getMessage());
        } catch (NoSuchElementException e) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND);
        }
        return "redirect:/pictures/" + id;
    }

    @PostMapping("/pictures/{id}/transfer")
    public String transferPicture(@PathVariable int id, @RequestParam int newOwnerId) {
        try {
            pictureService.transferOwnership(newOwnerId, id);
        } catch (NoSuchElementException e) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND);
        }
        return "redirect:/pictures/" + id;
    }

    @GetMapping("/delete")
    public String deleteForm() {
        return "delete"; // Returns delete.html
    }

    @PostMapping("/delete")
    public String deletePicture(@RequestParam int id, Model model) {
        // Vulnerable to Broken Access Control
        pictureService.delete(id);
        model.addAttribute("message", "Picture deleted");
        return "deleteResult"; // Returns deleteResult.html
    }
}
