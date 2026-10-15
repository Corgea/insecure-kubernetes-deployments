package com.example.catapp.controllers;

import com.example.catapp.models.Album;
import com.example.catapp.models.Album.Visibility;
import com.example.catapp.models.CatPicture;
import com.example.catapp.services.AccessStats;
import com.example.catapp.services.AccessStats.AccessType;
import com.example.catapp.services.AlbumService;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseBody;
import org.springframework.web.bind.annotation.SessionAttribute;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.stream.Collectors;

@Controller
public class AlbumController {

    private final AlbumService albumService;

    public AlbumController(AlbumService albumService) {
        this.albumService = albumService;
    }

    @GetMapping("/albums")
    public ResponseEntity<List<AlbumSummary>> myAlbums(
            @SessionAttribute(name = SessionKeys.USER_ID, required = false) Integer userId) {
        if (userId == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
        }
        return ResponseEntity.ok(summarize(albumService.albumsOwnedBy(userId)));
    }

    @GetMapping("/albums/public")
    @ResponseBody
    public List<AlbumSummary> publicAlbums() {
        return summarize(albumService.publicAlbums());
    }

    @PostMapping("/albums")
    public String create(@RequestParam String name,
                         @RequestParam(defaultValue = "PRIVATE") Visibility visibility,
                         @SessionAttribute(name = SessionKeys.USER_ID, required = false) Integer userId) {
        if (userId == null) {
            return "redirect:/login";
        }
        Album album = albumService.create(userId, name, visibility);
        return "redirect:/albums/" + album.getId();
    }

    @GetMapping("/albums/{id}")
    public String view(@PathVariable int id,
                       @SessionAttribute(name = SessionKeys.USER_ID, required = false) Integer userId,
                       Model model) {
        Album album = albumService.openAlbum(id, userId, AccessType.VIEW);
        // The album page reuses the picture grid from the search results page.
        model.addAttribute("pictures", albumService.pictures(album));
        return "searchResults";
    }

    @GetMapping("/albums/{id}/summary")
    @ResponseBody
    public AlbumSummary summary(@PathVariable int id,
                                @SessionAttribute(name = SessionKeys.USER_ID, required = false) Integer userId) {
        Album album = albumService.getVisibleAlbum(id, userId);
        int pictureCount = albumService.countPictures(album);
        return new AlbumSummary(album, pictureCount);
    }

    /**
     * Downloads the album as a plain-text list of picture URLs, one per line.
     */
    @GetMapping("/albums/{id}/download")
    public ResponseEntity<String> download(@PathVariable int id,
                                           @SessionAttribute(name = SessionKeys.USER_ID, required = false) Integer userId) {
        Album album = albumService.openAlbum(id, userId, AccessType.DOWNLOAD);
        String body = albumService.pictures(album).stream()
                .map(CatPicture::getUrl)
                .filter(Objects::nonNull)
                .map(url -> url + "\n")
                .collect(Collectors.joining());
        ContentDisposition disposition = ContentDisposition.attachment()
                .filename("album-" + album.getId() + ".txt")
                .build();
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, disposition.toString())
                .contentType(new MediaType("text", "plain", StandardCharsets.UTF_8))
                .body(body);
    }

    @GetMapping("/albums/{id}/stats")
    public ResponseEntity<AccessStats.Snapshot> stats(@PathVariable int id,
                                                      @SessionAttribute(name = SessionKeys.USER_ID, required = false) Integer userId) {
        if (userId == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
        }
        return ResponseEntity.ok(albumService.statsFor(id, userId));
    }

    @PostMapping("/albums/{id}/rename")
    public String rename(@PathVariable int id,
                         @RequestParam String name,
                         @SessionAttribute(name = SessionKeys.USER_ID, required = false) Integer userId) {
        if (userId == null) {
            return "redirect:/login";
        }
        albumService.rename(id, userId, name);
        return "redirect:/albums/" + id;
    }

    @PostMapping("/albums/{id}/visibility")
    public String changeVisibility(@PathVariable int id,
                                   @RequestParam Visibility visibility,
                                   @SessionAttribute(name = SessionKeys.USER_ID, required = false) Integer userId) {
        if (userId == null) {
            return "redirect:/login";
        }
        albumService.changeVisibility(id, userId, visibility);
        return "redirect:/albums/" + id;
    }

    @PostMapping("/albums/{id}/pictures")
    public String addPicture(@PathVariable int id,
                             @RequestParam int pictureId,
                             @SessionAttribute(name = SessionKeys.USER_ID, required = false) Integer userId) {
        if (userId == null) {
            return "redirect:/login";
        }
        albumService.addPicture(id, userId, pictureId);
        return "redirect:/albums/" + id;
    }

    @PostMapping("/albums/{id}/pictures/{pictureId}/remove")
    public String removePicture(@PathVariable int id,
                                @PathVariable int pictureId,
                                @SessionAttribute(name = SessionKeys.USER_ID, required = false) Integer userId) {
        if (userId == null) {
            return "redirect:/login";
        }
        albumService.removePicture(id, userId, pictureId);
        return "redirect:/albums/" + id;
    }

    @PostMapping("/albums/{id}/delete")
    public String delete(@PathVariable int id,
                         @SessionAttribute(name = SessionKeys.USER_ID, required = false) Integer userId) {
        if (userId == null) {
            return "redirect:/login";
        }
        try {
            albumService.delete(id, userId);
            return "redirect:/albums";
        } catch (Exception e) {
            // A double-submitted delete ends up here once the first one went through; the album
            // list is the right place to land either way.
            return "redirect:/albums";
        }
    }

    @PostMapping("/albums/merge")
    public String merge(@SessionAttribute(name = SessionKeys.USER_ID, required = false) Integer userId) {
        if (userId == null) {
            return "redirect:/login";
        }
        albumService.mergeAlbums(userId);
        return "redirect:/albums";
    }

    private List<AlbumSummary> summarize(List<Album> albums) {
        Map<Integer, Integer> counts = albumService.pictureCounts(albums);
        return albums.stream()
                .map(album -> new AlbumSummary(album, counts.getOrDefault(album.getId(), 0)))
                .collect(Collectors.toList());
    }
}
