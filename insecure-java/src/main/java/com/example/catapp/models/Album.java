package com.example.catapp.models;

import javax.persistence.CollectionTable;
import javax.persistence.Column;
import javax.persistence.ElementCollection;
import javax.persistence.Entity;
import javax.persistence.EnumType;
import javax.persistence.Enumerated;
import javax.persistence.GeneratedValue;
import javax.persistence.GenerationType;
import javax.persistence.Id;
import javax.persistence.JoinColumn;
import javax.persistence.PrePersist;
import javax.persistence.Table;
import java.time.Instant;
import java.util.LinkedHashSet;
import java.util.Objects;
import java.util.Set;

@Entity
@Table(name = "albums")
public class Album {

    public enum Visibility {
        /** Only the owner can open the album. */
        PRIVATE,
        /** Anyone with the album id can open it, but it is not listed publicly. */
        UNLISTED,
        /** Listed on the public albums page. */
        PUBLIC
    }

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    @Column(nullable = false, length = 100)
    private String name;

    @Column(nullable = false)
    private Integer ownerId;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 16)
    private Visibility visibility = Visibility.PRIVATE;

    @ElementCollection
    @CollectionTable(name = "album_pictures", joinColumns = @JoinColumn(name = "album_id"))
    @Column(name = "picture_id", nullable = false)
    private Set<Integer> pictureIds = new LinkedHashSet<>();

    @Column(nullable = false, updatable = false)
    private Instant createdAt;

    @PrePersist
    void onCreate() {
        if (createdAt == null) {
            createdAt = Instant.now();
        }
    }

    public Integer getId() {
        return id;
    }

    public void setId(Integer id) {
        this.id = id;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public Integer getOwnerId() {
        return ownerId;
    }

    public void setOwnerId(Integer ownerId) {
        this.ownerId = ownerId;
    }

    public Visibility getVisibility() {
        return visibility;
    }

    public void setVisibility(Visibility visibility) {
        this.visibility = visibility;
    }

    public Set<Integer> getPictureIds() {
        return pictureIds;
    }

    public void setPictureIds(Set<Integer> pictureIds) {
        this.pictureIds = pictureIds;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(Instant createdAt) {
        this.createdAt = createdAt;
    }

    /**
     * Albums are equal when they belong to the same owner and carry the same name, which is how
     * users tell their albums apart.
     */
    @Override
    public boolean equals(Object o) {
        if (this == o) {
            return true;
        }
        if (!(o instanceof Album)) {
            return false;
        }
        Album other = (Album) o;
        return Objects.equals(ownerId, other.ownerId) && Objects.equals(name, other.name);
    }

    @Override
    public String toString() {
        return "Album{id=" + id + ", ownerId=" + ownerId + ", name='" + name + "', visibility=" + visibility + "}";
    }
}
