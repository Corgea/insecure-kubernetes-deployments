package com.example.catapp.models;

import javax.persistence.*;

@Entity
@Table(name = "comments")
public class Comment {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private int id;

    @Column(columnDefinition = "TEXT")
    private String text;

    private int reportCount;

    private boolean hidden;

    // Getters and Setters

    public int getId() {
        return id;
    }

    // ... other getters and setters

    public void setId(int id) {
        this.id = id;
    }

	public String getText() {
		return text;
	}

	public void setText(String text) {
		this.text = text;
	}

	public int getReportCount() {
		return reportCount;
	}

	public void setReportCount(int reportCount) {
		this.reportCount = reportCount;
	}

	public boolean isHidden() {
		return hidden;
	}

	public void setHidden(boolean hidden) {
		this.hidden = hidden;
	}
}
