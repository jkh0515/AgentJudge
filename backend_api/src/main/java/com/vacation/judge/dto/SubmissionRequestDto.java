package com.vacation.judge.dto;

import lombok.Getter;
import lombok.Setter;
import java.util.List;

@Getter
@Setter
public class SubmissionRequestDto {
    private Long userId;
    private String problemText;
    private String code;
    private String language;
    private List<TestCaseDto> testCases;
}
