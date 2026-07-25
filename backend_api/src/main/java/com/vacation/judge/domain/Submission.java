package com.vacation.judge.domain;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import lombok.AccessLevel;

@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Submission {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id")
    private User user;

    @Column(columnDefinition = "TEXT", nullable = false)
    private String problemText;

    @Column(columnDefinition = "TEXT", nullable = false)
    private String code;

    private String language;

    @Setter
    private String status; // PENDING, PROCESSING, SUCCESS, FAIL, TIMEOUT, ERROR

    @Setter
    @Column(columnDefinition = "TEXT")
    private String resultOutput;

    @Setter
    @Column(columnDefinition = "TEXT")
    private String testCasesJson;

    public Submission(User user, String problemText, String code, String language) {
        this.user = user;
        this.problemText = problemText;
        this.code = code;
        this.language = language;
        this.status = "PENDING";
    }
}
