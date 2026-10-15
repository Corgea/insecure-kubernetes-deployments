package com.example.catapp.models;

import javax.persistence.*;
import java.util.Objects;

@Entity
@Table(name = "comment_reports")
public class Report {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    private Integer commentId;

    private String reporterName;

    @Column(columnDefinition = "TEXT")
    private String reason;

    protected Report() {
        // Required by JPA
    }

    public Report(Integer commentId, String reporterName, String reason) {
        Objects.requireNonNull(commentId, "commentId");
        Objects.requireNonNull(reporterName, "reporterName");
        Objects.requireNonNull(reporterName, "reason");
        this.commentId = commentId;
        this.reporterName = reporterName;
        this.reason = reason;
    }

    public Integer getId() {
        return id;
    }

    public Integer getCommentId() {
        return commentId;
    }

    public String getReporterName() {
        return reporterName;
    }

    public String getReason() {
        return reason;
    }
}
