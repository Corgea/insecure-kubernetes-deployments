package com.example.catapp.repositories;

import com.example.catapp.models.ShareLink;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface ShareLinkRepository extends JpaRepository<ShareLink, Integer> {

    Optional<ShareLink> findByToken(String token);

    List<ShareLink> findByAlbumIdOrderByCreatedAtDesc(Integer albumId);

    void deleteByAlbumId(Integer albumId);

    /** Points every share link of one album at another album. Returns the number of links moved. */
    @Modifying
    @Query("update ShareLink l set l.albumId = :to where l.albumId = :from")
    int moveToAlbum(@Param("from") Integer fromAlbumId, @Param("to") Integer toAlbumId);
}
