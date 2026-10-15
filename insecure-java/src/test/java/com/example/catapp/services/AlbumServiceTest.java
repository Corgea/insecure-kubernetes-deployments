package com.example.catapp.services;

import com.example.catapp.models.Album;
import com.example.catapp.models.Album.Visibility;
import com.example.catapp.models.CatPicture;
import com.example.catapp.repositories.AlbumRepository;
import com.example.catapp.repositories.CatPictureRepository;
import com.example.catapp.repositories.ShareLinkRepository;
import com.example.catapp.services.AccessStats.AccessType;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyCollection;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class AlbumServiceTest {

    private static final int ALBUM_ID = 42;
    private static final int OWNER_ID = 7;
    private static final int OTHER_USER_ID = 8;

    @Mock
    private AlbumRepository albumRepository;

    @Mock
    private CatPictureRepository catPictureRepository;

    @Mock
    private ShareLinkRepository shareLinkRepository;

    private AccessStats accessStats;
    private AlbumService albumService;

    @BeforeEach
    void setUp() {
        accessStats = new AccessStats();
        albumService = new AlbumService(albumRepository, catPictureRepository, shareLinkRepository, accessStats);
    }

    @Test
    void privateAlbumIsVisibleOnlyToItsOwner() {
        Album album = album(Visibility.PRIVATE);

        assertTrue(albumService.canView(album, OWNER_ID));
        assertFalse(albumService.canView(album, OTHER_USER_ID));
        assertFalse(albumService.canView(album, null));
    }

    @Test
    void unlistedAndPublicAlbumsAreVisibleToEveryone() {
        assertTrue(albumService.canView(album(Visibility.UNLISTED), null));
        assertTrue(albumService.canView(album(Visibility.PUBLIC), OTHER_USER_ID));
    }

    @Test
    void privateAlbumOfAnotherUserIsReportedAsMissing() {
        when(albumRepository.findById(ALBUM_ID)).thenReturn(Optional.of(album(Visibility.PRIVATE)));

        assertThrows(AlbumNotFoundException.class, () -> albumService.getVisibleAlbum(ALBUM_ID, OTHER_USER_ID));
    }

    @Test
    void onlyTheOwnerCanRenameAnAlbum() {
        when(albumRepository.findById(ALBUM_ID)).thenReturn(Optional.of(album(Visibility.PUBLIC)));

        assertThrows(AlbumNotFoundException.class, () -> albumService.rename(ALBUM_ID, OTHER_USER_ID, "Mine now"));
        verify(albumRepository, never()).save(any());
    }

    @Test
    void createTrimsTheNameAndDefaultsToPrivate() {
        when(albumRepository.save(any(Album.class))).thenAnswer(invocation -> invocation.getArgument(0));

        Album album = albumService.create(OWNER_ID, "  Garden cats  ", null);

        assertEquals("Garden cats", album.getName());
        assertEquals(Visibility.PRIVATE, album.getVisibility());
        assertEquals(OWNER_ID, album.getOwnerId());
    }

    @Test
    void createRejectsBlankAndOverlongNames() {
        assertThrows(AlbumValidationException.class,
                () -> albumService.create(OWNER_ID, "   ", Visibility.PUBLIC));
        assertThrows(AlbumValidationException.class,
                () -> albumService.create(OWNER_ID, "x".repeat(AlbumService.MAX_NAME_LENGTH + 1), Visibility.PUBLIC));
        verify(albumRepository, never()).save(any());
    }

    @Test
    void addPictureRejectsPicturesOfOtherUsers() {
        when(albumRepository.findById(ALBUM_ID)).thenReturn(Optional.of(album(Visibility.PRIVATE)));
        when(catPictureRepository.findById(5)).thenReturn(Optional.of(picture(5, OTHER_USER_ID)));

        assertThrows(AlbumValidationException.class, () -> albumService.addPicture(ALBUM_ID, OWNER_ID, 5));
        verify(albumRepository, never()).save(any());
    }

    @Test
    void addPictureStoresThePictureId() {
        Album album = album(Visibility.PRIVATE);
        when(albumRepository.findById(ALBUM_ID)).thenReturn(Optional.of(album));
        when(catPictureRepository.findById(5)).thenReturn(Optional.of(picture(5, OWNER_ID)));
        when(albumRepository.save(album)).thenReturn(album);

        albumService.addPicture(ALBUM_ID, OWNER_ID, 5);

        assertEquals(Set.of(5), album.getPictureIds());
    }

    @Test
    void countPicturesReturnsTheCountFromTheDatabase() {
        Album album = album(Visibility.PRIVATE);
        when(albumRepository.countPictures(anyCollection())).thenReturn(List.of(pictureCount(ALBUM_ID, 3)));

        assertEquals(3, albumService.countPictures(album));
    }

    @Test
    void deleteRemovesShareLinksAndStats() {
        Album album = album(Visibility.PRIVATE);
        when(albumRepository.findById(ALBUM_ID)).thenReturn(Optional.of(album));
        accessStats.recordAccess(ALBUM_ID, AccessType.VIEW, OWNER_ID);

        albumService.delete(ALBUM_ID, OWNER_ID);

        verify(shareLinkRepository).deleteByAlbumId(ALBUM_ID);
        verify(albumRepository).delete(album);
        assertEquals(0L, accessStats.snapshot(ALBUM_ID).getViews());
    }

    @Test
    void openingAnAlbumCountsAView() {
        when(albumRepository.findById(ALBUM_ID)).thenReturn(Optional.of(album(Visibility.PUBLIC)));

        albumService.openAlbum(ALBUM_ID, OTHER_USER_ID, AccessType.VIEW);
        albumService.openAlbum(ALBUM_ID, null, AccessType.VIEW);

        assertEquals(2L, accessStats.snapshot(ALBUM_ID).getViews());
    }

    @Test
    void refusedOpenIsNotCounted() {
        when(albumRepository.findById(ALBUM_ID)).thenReturn(Optional.of(album(Visibility.PRIVATE)));

        assertThrows(AlbumNotFoundException.class,
                () -> albumService.openAlbum(ALBUM_ID, OTHER_USER_ID, AccessType.VIEW));
        assertEquals(0L, accessStats.snapshot(ALBUM_ID).getViews());
    }

    @Test
    void viewsFromOtherThreadsAreCounted() {
        when(albumRepository.findById(ALBUM_ID)).thenReturn(Optional.of(album(Visibility.PUBLIC)));

        // AccessStats is shared by every request thread, so record from a thread of its own.
        Thread viewer = new Thread(() -> albumService.openAlbum(ALBUM_ID, null, AccessType.VIEW));
        viewer.start();

        assertEquals(1L, accessStats.snapshot(ALBUM_ID).getViews());
    }

    private static Album album(Visibility visibility) {
        Album album = new Album();
        album.setId(ALBUM_ID);
        album.setOwnerId(OWNER_ID);
        album.setName("Garden cats");
        album.setVisibility(visibility);
        album.setCreatedAt(Instant.parse("2024-05-01T10:00:00Z"));
        return album;
    }

    private static CatPicture picture(int id, int ownerId) {
        CatPicture picture = new CatPicture();
        picture.setId(id);
        picture.setName("Picture " + id);
        picture.setUrl("https://example.com/cats/" + id + ".jpg");
        picture.setOwnerId(ownerId);
        return picture;
    }

    private static AlbumRepository.PictureCount pictureCount(int albumId, long pictures) {
        return new AlbumRepository.PictureCount() {
            @Override
            public Integer getAlbumId() {
                return albumId;
            }

            @Override
            public Long getPictures() {
                return pictures;
            }
        };
    }
}
