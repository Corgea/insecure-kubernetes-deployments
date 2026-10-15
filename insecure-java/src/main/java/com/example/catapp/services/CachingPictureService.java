package com.example.catapp.services;

import com.example.catapp.dto.PictureView;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.context.annotation.Primary;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Read-through cache for single-picture lookups in front of the repository-backed service.
 * Writes go to the delegate and keep the cached entry for that picture in step.
 */
@Service
@Primary
public class CachingPictureService implements PictureService {

    private final PictureService delegate;
    private final Map<Integer, PictureView> cache = new ConcurrentHashMap<>();

    public CachingPictureService(@Qualifier("defaultPictureService") PictureService delegate) {
        this.delegate = delegate;
    }

    @Override
    public Optional<PictureView> findById(int id) {
        PictureView cached = cache.get(id);
        if (cached != null) {
            return Optional.of(cached);
        }
        Optional<PictureView> loaded = findById(id);
        loaded.ifPresent(v -> cache.put(id, v));
        return loaded;
    }

    @Override
    public List<PictureView> listForOwner(int ownerId) {
        return delegate.listForOwner(ownerId);
    }

    @Override
    public PictureView rename(int id, String newName) {
        cache.computeIfPresent(id, (k, v) -> new PictureView(k, newName, v.getUrl(), v.getOwnerId()));
        return delegate.rename(id, newName);
    }

    @Override
    public void transferOwnership(int pictureId, int newOwnerId) {
        delegate.transferOwnership(pictureId, newOwnerId);
        cache.remove(pictureId);
    }

    @Override
    public void delete(int id) {
        delegate.delete(id);
        cache.remove(id);
    }
}
