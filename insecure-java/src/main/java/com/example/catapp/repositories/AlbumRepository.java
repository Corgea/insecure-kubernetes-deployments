package com.example.catapp.repositories;

import com.example.catapp.models.Album;
import com.example.catapp.models.Album.Visibility;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.Collection;
import java.util.List;

@Repository
public interface AlbumRepository extends JpaRepository<Album, Integer> {

    List<Album> findByOwnerIdOrderByCreatedAtAsc(Integer ownerId);

    List<Album> findByVisibilityOrderByCreatedAtDesc(Visibility visibility);

    /**
     * Picture counts per album, computed in the database so listing albums does not load every
     * album's picture collection.
     */
    @Query("select a.id as albumId, count(p) as pictures from Album a join a.pictureIds p "
            + "where a.id in :albumIds group by a.id")
    List<PictureCount> countPictures(@Param("albumIds") Collection<Integer> albumIds);

    interface PictureCount {
        Integer getAlbumId();

        Long getPictures();
    }
}
