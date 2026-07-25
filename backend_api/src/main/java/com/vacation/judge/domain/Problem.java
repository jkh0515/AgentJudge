package com.vacation.judge.domain;

import java.util.ArrayList;
import java.util.List;
import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.AccessLevel;

@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Problem {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String title;

    @Column(columnDefinition = "TEXT")
    private String description;

    @Column(columnDefinition = "TEXT")
    private String code;
    
    private int timeLimitMs;
    private int memoryLimitMb;
    
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id")
    private User user;
    
    @OneToMany(mappedBy = "problem", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<TestCase> testCases = new ArrayList<>();

    public Problem(User user, String title, String description, String code, int timeLimitMs, int memoryLimitMb) {
        this.user = user;
        this.title = title;
        this.description = description;
        this.code = code;
        this.timeLimitMs = timeLimitMs;
        this.memoryLimitMb = memoryLimitMb;
    }

    public void addTestCase(TestCase testCase) {
        this.testCases.add(testCase);
        testCase.setProblem(this);
    }

    public void updateProblem(String title, String description, String code, int timeLimitMs, int memoryLimitMb) {
        this.title = title;
        this.description = description;
        this.code = code;
        this.timeLimitMs = timeLimitMs;
        this.memoryLimitMb = memoryLimitMb;
    }
}

