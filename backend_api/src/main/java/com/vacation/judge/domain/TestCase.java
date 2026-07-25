package com.vacation.judge.domain;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import lombok.AccessLevel;

@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class TestCase {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "problem_id", nullable = false)
    @Setter
    private Problem problem;

    @Column(columnDefinition = "TEXT", nullable = false)
    private String inputData;

    @Column(columnDefinition = "TEXT", nullable = false)
    private String expectedOutput;

    private int sequenceIndex;

    public TestCase(Problem problem, String inputData, String expectedOutput, int sequenceIndex) {
        this.problem = problem;
        this.inputData = inputData;
        this.expectedOutput = expectedOutput;
        this.sequenceIndex = sequenceIndex;
    }
}
