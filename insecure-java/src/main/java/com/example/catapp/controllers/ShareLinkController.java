package com.example.catapp.controllers;

import com.example.catapp.models.Album;
import com.example.catapp.models.ShareLink;
import com.example.catapp.services.AlbumNotFoundException;
import com.example.catapp.services.AlbumService;
import com.example.catapp.services.AlbumValidationException;
import com.example.catapp.services.ShareLinkService;
import com.example.catapp.services.ShareLinkUnavailableException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseBody;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.SessionAttribute;

import java.time.Duration;
import java.util.List;
import java.util.stream.Collectors;

@Controller
public class ShareLinkController {

    private final ShareLinkService shareLinkService;
    private final AlbumService albumService;

    public ShareLinkController(ShareLinkService shareLinkService, AlbumService albumService) {
        this.shareLinkService = shareLinkService;
        this.albumService = albumService;
    }

    @PostMapping("/albums/{id}/share")
    public ResponseEntity<ShareLinkView> create(@PathVariable int id,
                                                @RequestParam(defaultValue = "72") int ttlHours,
                                                @RequestParam(defaultValue = "false") boolean oneTime,
                                                @SessionAttribute(name = SessionKeys.USER_ID, required = false) Integer userId) {
        if (userId == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
        }
        ShareLink link = shareLinkService.create(id, userId, Duration.ofHours(ttlHours), oneTime);
        return ResponseEntity.status(HttpStatus.CREATED).body(new ShareLinkView(link));
    }

    @GetMapping("/albums/{id}/share")
    public ResponseEntity<List<ShareLinkView>> list(@PathVariable int id,
                                                    @SessionAttribute(name = SessionKeys.USER_ID, required = false) Integer userId) {
        if (userId == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
        }
        List<ShareLinkView> links = shareLinkService.activeLinks(id, userId).stream()
                .map(ShareLinkView::new)
                .collect(Collectors.toList());
        return ResponseEntity.ok(links);
    }

    @PostMapping("/albums/{id}/share/{linkId}/revoke")
    public ResponseEntity<Void> revoke(@PathVariable int id,
                                       @PathVariable int linkId,
                                       @SessionAttribute(name = SessionKeys.USER_ID, required = false) Integer userId) {
        if (userId == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
        }
        shareLinkService.revoke(id, linkId, userId);
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/shared/{token}")
    public String open(@PathVariable String token, Model model) {
        Album album = shareLinkService.redeem(token);
        model.addAttribute("pictures", albumService.pictures(album));
        return "searchResults";
    }

    @ExceptionHandler(ShareLinkUnavailableException.class)
    @ResponseStatus(HttpStatus.NOT_FOUND)
    @ResponseBody
    public String shareLinkUnavailable(ShareLinkUnavailableException e) {
        return e.getMessage();
    }

    @ExceptionHandler(AlbumNotFoundException.class)
    @ResponseStatus(HttpStatus.NOT_FOUND)
    @ResponseBody
    public String albumNotFound(AlbumNotFoundException e) {
        return e.getMessage();
    }

    @ExceptionHandler(AlbumValidationException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    @ResponseBody
    public String invalidShareRequest(AlbumValidationException e) {
        return e.getMessage();
    }
}
