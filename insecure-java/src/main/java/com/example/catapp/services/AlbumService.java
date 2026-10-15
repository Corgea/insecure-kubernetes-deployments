package com.example.catapp.services;

import com.example.catapp.models.Album;
import com.example.catapp.models.Album.Visibility;
import com.example.catapp.models.CatPicture;
import com.example.catapp.repositories.AlbumRepository;
import com.example.catapp.repositories.CatPictureRepository;
import com.example.catapp.repositories.ShareLinkRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

@Service
public class AlbumService {

    static final int MAX_NAME_LENGTH = 100;

    private final AlbumRepository albumRepository;
    private final CatPictureRepository catPictureRepository;
    private final ShareLinkRepository shareLinkRepository;

    public AlbumService(AlbumRepository albumRepository,
                        CatPictureRepository catPictureRepository,
                        ShareLinkRepository shareLinkRepository) {
        this.albumRepository = albumRepository;
        this.catPictureRepository = catPictureRepository;
        this.shareLinkRepository = shareLinkRepository;
    }

    public List<Album> albumsOwnedBy(int userId) {
        return albumRepository.findByOwnerIdOrderByCreatedAtAsc(userId);
    }

    public List<Album> publicAlbums() {
        return albumRepository.findByVisibilityOrderByCreatedAtDesc(Visibility.PUBLIC);
    }

    @Transactional
    public Album create(int ownerId, String name, Visibility visibility) {
        Album album = new Album();
        album.setOwnerId(ownerId);
        album.setName(validName(name));
        album.setVisibility(visibility == null ? Visibility.PRIVATE : visibility);
        return albumRepository.save(album);
    }

    /**
     * Loads an album the user may look at. Albums the user may not see are reported as missing.
     */
    public Album getVisibleAlbum(int albumId, Integer userId) {
        return albumRepository.findById(albumId)
                .filter(album -> canView(album, userId))
                .orElseThrow(() -> new AlbumNotFoundException(albumId));
    }

    /**
     * Loads an album owned by the user. Albums owned by someone else are reported as missing.
     */
    public Album getOwnedAlbum(int albumId, int userId) {
        return albumRepository.findById(albumId)
                .filter(album -> isOwner(album, userId))
                .orElseThrow(() -> new AlbumNotFoundException(albumId));
    }

    /**
     * Private albums are visible to their owner only; unlisted and public albums to anyone. Share
     * links do not go through this check, see {@link ShareLinkService#redeem(String)}.
     */
    public boolean canView(Album album, Integer userId) {
        if (album.getVisibility() == Visibility.PRIVATE) {
            return isOwner(album, userId);
        }
        return true;
    }

    public boolean isOwner(Album album, Integer userId) {
        return userId != null && Objects.equals(album.getOwnerId(), userId);
    }

    @Transactional
    public Album rename(int albumId, int userId, String name) {
        Album album = getOwnedAlbum(albumId, userId);
        album.setName(validName(name));
        return albumRepository.save(album);
    }

    @Transactional
    public Album changeVisibility(int albumId, int userId, Visibility visibility) {
        if (visibility == null) {
            throw new AlbumValidationException("Visibility is required");
        }
        Album album = getOwnedAlbum(albumId, userId);
        album.setVisibility(visibility);
        return albumRepository.save(album);
    }

    /**
     * Adds one of the user's own pictures to one of the user's albums. Adding a picture twice is a
     * no-op.
     */
    @Transactional
    public Album addPicture(int albumId, int userId, int pictureId) {
        Album album = getOwnedAlbum(albumId, userId);
        CatPicture picture = catPictureRepository.findById(pictureId)
                .filter(p -> p.getOwnerId() == userId)
                .orElseThrow(() -> new AlbumValidationException("Picture " + pictureId + " is not one of your pictures"));
        album.getPictureIds().add(picture.getId());
        return albumRepository.save(album);
    }

    @Transactional
    public Album removePicture(int albumId, int userId, int pictureId) {
        Album album = getOwnedAlbum(albumId, userId);
        album.getPictureIds().remove(Integer.valueOf(pictureId));
        return albumRepository.save(album);
    }

    /**
     * Pictures in the album that still exist. Ids of pictures deleted since they were added are
     * skipped.
     */
    @Transactional(readOnly = true)
    public List<CatPicture> pictures(Album album) {
        return catPictureRepository.findAllById(album.getPictureIds());
    }

    /**
     * Number of pictures in {@code album}, counted by the database. Never null.
     */
    public Integer countPictures(Album album) {
        return pictureCounts(Collections.singletonList(album)).get(album.getId());
    }

    /**
     * Picture counts for several albums in one query, keyed by album id.
     */
    public Map<Integer, Integer> pictureCounts(Collection<Album> albums) {
        if (albums.isEmpty()) {
            return Collections.emptyMap();
        }
        List<Integer> albumIds = albums.stream().map(Album::getId).collect(Collectors.toList());
        Map<Integer, Integer> counts = new HashMap<>();
        for (AlbumRepository.PictureCount row : albumRepository.countPictures(albumIds)) {
            counts.put(row.getAlbumId(), Math.toIntExact(row.getPictures()));
        }
        return counts;
    }

    @Transactional
    public void delete(int albumId, int userId) {
        Album album = getOwnedAlbum(albumId, userId);
        shareLinkRepository.deleteByAlbumId(album.getId());
        albumRepository.delete(album);
    }

    /**
     * Folds the user's albums that share a name into the oldest of them, for example after a
     * double-submitted create form. Returns the number of albums merged away.
     */
    @Transactional
    public int mergeAlbums(int ownerId) {
        List<Album> albums = albumRepository.findByOwnerIdOrderByCreatedAtAsc(ownerId);
        Set<Album> seen = new HashSet<>();
        List<Album> duplicates = new ArrayList<>();
        for (Album album : albums) {
            if (!seen.add(album)) {
                duplicates.add(album);
            }
        }
        for (Album duplicate : duplicates) {
            // Albums are ordered oldest first, so the first equal album is the one we keep.
            Album original = albums.stream().filter(duplicate::equals).findFirst().orElseThrow();
            original.getPictureIds().addAll(duplicate.getPictureIds());
            // Links already handed out for the duplicate keep working and open the merged album.
            shareLinkRepository.moveToAlbum(duplicate.getId(), original.getId());
            albumRepository.delete(duplicate);
        }
        return duplicates.size();
    }

    private static String validName(String name) {
        String trimmed = name == null ? "" : name.trim();
        if (trimmed.isEmpty()) {
            throw new AlbumValidationException("Album name is required");
        }
        if (trimmed.length() > MAX_NAME_LENGTH) {
            throw new AlbumValidationException("Album names are at most " + MAX_NAME_LENGTH + " characters");
        }
        return trimmed;
    }
}
