package com.example.catapp.services;

import com.example.catapp.dto.PictureView;
import com.example.catapp.models.CatPicture;
import com.example.catapp.repositories.CatPictureRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.NoSuchElementException;
import java.util.Optional;
import java.util.stream.Collectors;

@Service("defaultPictureService")
public class DefaultPictureService implements PictureService {

    private final CatPictureRepository catPictureRepository;

    public DefaultPictureService(CatPictureRepository catPictureRepository) {
        this.catPictureRepository = catPictureRepository;
    }

    @Override
    public Optional<PictureView> findById(int id) {
        return catPictureRepository.findById(id).map(PictureView::from);
    }

    @Override
    public List<PictureView> listForOwner(int ownerId) {
        return catPictureRepository.findByOwnerId(ownerId).stream()
                .map(PictureView::from)
                .collect(Collectors.toList());
    }

    @Override
    @Transactional
    public PictureView rename(int id, String newName) {
        if (newName == null || newName.isBlank()) {
            throw new IllegalArgumentException("Picture name must not be blank");
        }
        CatPicture picture = loadPicture(id);
        picture.setName(newName);
        return PictureView.from(catPictureRepository.save(picture));
    }

    @Override
    @Transactional
    public void transferOwnership(int pictureId, int newOwnerId) {
        CatPicture picture = loadPicture(pictureId);
        picture.setOwnerId(newOwnerId);
        catPictureRepository.save(picture);
    }

    @Override
    public void delete(int id) {
        catPictureRepository.deleteById(id);
    }

    private CatPicture loadPicture(int id) {
        return catPictureRepository.findById(id)
                .orElseThrow(() -> new NoSuchElementException("No picture with id " + id));
    }
}
