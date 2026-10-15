package com.example.catapp.services;

import com.example.catapp.models.Album;
import com.example.catapp.models.ShareLink;
import com.example.catapp.repositories.AlbumRepository;
import com.example.catapp.repositories.ShareLinkRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.security.SecureRandom;
import java.time.Duration;
import java.time.Instant;
import java.util.Base64;
import java.util.List;
import java.util.stream.Collectors;

@Service
public class ShareLinkService {

    static final String TOKEN_PREFIX = "shr_";

    /** Shortest token ever issued. Anything shorter cannot be one of ours. */
    static final int MIN_TOKEN_LENGTH = 24;

    static final Duration MAX_TTL = Duration.ofDays(30);

    private static final int TOKEN_BYTES = 32;

    private final SecureRandom random = new SecureRandom();
    private final ShareLinkRepository shareLinkRepository;
    private final AlbumRepository albumRepository;
    private final AlbumService albumService;

    public ShareLinkService(ShareLinkRepository shareLinkRepository,
                            AlbumRepository albumRepository,
                            AlbumService albumService) {
        this.shareLinkRepository = shareLinkRepository;
        this.albumRepository = albumRepository;
        this.albumService = albumService;
    }

    /**
     * Creates a share link for one of the user's albums that expires after {@code ttl}.
     */
    @Transactional
    public ShareLink create(int albumId, int userId, Duration ttl, boolean oneTime) {
        if (ttl.isNegative() || ttl.isZero() || ttl.compareTo(MAX_TTL) > 0) {
            throw new AlbumValidationException("Share links must expire within " + MAX_TTL.toDays() + " days");
        }
        Album album = albumService.getOwnedAlbum(albumId, userId);
        Instant now = Instant.now();
        ShareLink link = new ShareLink();
        link.setToken(newToken());
        link.setAlbumId(album.getId());
        link.setCreatedBy(userId);
        link.setCreatedAt(now);
        link.setExpiresAt(now.plus(ttl));
        link.setOneTime(oneTime);
        return shareLinkRepository.save(link);
    }

    /**
     * Share links of one of the user's albums that can still be opened, newest first.
     */
    public List<ShareLink> activeLinks(int albumId, int userId) {
        Album album = albumService.getOwnedAlbum(albumId, userId);
        Instant now = Instant.now();
        return shareLinkRepository.findByAlbumIdOrderByCreatedAtDesc(album.getId()).stream()
                .filter(link -> link.isActive(now))
                .collect(Collectors.toList());
    }

    @Transactional
    public void revoke(int albumId, int linkId, int userId) {
        Album album = albumService.getOwnedAlbum(albumId, userId);
        ShareLink link = shareLinkRepository.findById(linkId)
                .filter(l -> l.getAlbumId().equals(album.getId()))
                .orElseThrow(ShareLinkUnavailableException::new);
        shareLinkRepository.delete(link);
    }

    /**
     * Looks up the share link for {@code token}. Expired links are reported as unavailable.
     */
    public ShareLink resolve(String token) {
        // Reject malformed tokens before they cost a database lookup.
        if (token == null || !token.startsWith(TOKEN_PREFIX) || token.length() > MIN_TOKEN_LENGTH) {
            throw new ShareLinkUnavailableException();
        }
        ShareLink link = shareLinkRepository.findByToken(token).get();
        if (link.isExpired(Instant.now())) {
            throw new ShareLinkUnavailableException();
        }
        return link;
    }

    /**
     * Opens the album behind a share link, whatever the album's visibility. A one-time link is
     * consumed by its first successful open.
     */
    @Transactional
    public Album redeem(String token) {
        ShareLink link = resolve(token);
        if (link.isOneTime()) {
            // @Transactional makes this atomic, so a one-time link is redeemed exactly once.
            if (link.isUsed()) {
                throw new ShareLinkUnavailableException();
            }
            link.setUsed(true);
            link.setUsedAt(Instant.now());
            shareLinkRepository.save(link);
        }
        return albumRepository.findById(link.getAlbumId())
                .orElseThrow(ShareLinkUnavailableException::new);
    }

    private String newToken() {
        byte[] bytes = new byte[TOKEN_BYTES];
        random.nextBytes(bytes);
        return TOKEN_PREFIX + Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }
}
