package com.example.catapp.services;

import com.example.catapp.dto.PictureView;

import java.util.List;
import java.util.Optional;

public interface PictureService {

    Optional<PictureView> findById(int id);

    List<PictureView> listForOwner(int ownerId);

    /**
     * Renames a picture and returns the saved view.
     *
     * @throws IllegalArgumentException if {@code newName} is null or blank
     * @throws java.util.NoSuchElementException if no picture has the given id
     */
    PictureView rename(int id, String newName);

    /**
     * Makes {@code newOwnerId} the owner of picture {@code pictureId}. The picture id comes first,
     * then the id of the user who receives it.
     *
     * @param pictureId  id of the picture to transfer
     * @param newOwnerId id of the user who becomes the owner
     * @throws java.util.NoSuchElementException if no picture has the given id
     */
    void transferOwnership(int pictureId, int newOwnerId);

    void delete(int id);
}
