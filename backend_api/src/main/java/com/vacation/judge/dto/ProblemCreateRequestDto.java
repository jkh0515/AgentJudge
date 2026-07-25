package com.vacation.judge.dto;

import java.util.List;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
public class ProblemCreateRequestDto {
    private String title;
    private String description;
    private String code;
    private int timeLimitMs;
    private int memoryLimitMb;
    private List<TestCaseDto> testCases;
}
