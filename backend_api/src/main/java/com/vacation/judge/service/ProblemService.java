package com.vacation.judge.service;

import com.vacation.judge.domain.Problem;
import com.vacation.judge.domain.TestCase;
import com.vacation.judge.domain.User;
import com.vacation.judge.dto.ProblemCreateRequestDto;
import com.vacation.judge.dto.ProblemDto;
import com.vacation.judge.dto.TestCaseDto;
import com.vacation.judge.repository.ProblemRepository;
import com.vacation.judge.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class ProblemService {

    private final ProblemRepository problemRepository;
    private final UserRepository userRepository;

    @Transactional
    public ProblemDto saveProblem(ProblemCreateRequestDto request, Long userId) {
        User user = null;
        if (userId != null) {
            user = userRepository.findById(userId).orElse(null);
        }
        Problem problem = new Problem(
                user,
                request.getTitle() != null && !request.getTitle().trim().isEmpty() ? request.getTitle() : "제목 없는 문제",
                request.getDescription() != null ? request.getDescription() : "",
                request.getCode() != null ? request.getCode() : "",
                request.getTimeLimitMs() > 0 ? request.getTimeLimitMs() : 2000,
                request.getMemoryLimitMb() > 0 ? request.getMemoryLimitMb() : 256
        );

        if (request.getTestCases() != null) {
            int idx = 0;
            for (TestCaseDto tcDto : request.getTestCases()) {
                TestCase tc = new TestCase(
                        problem, 
                        tcDto.getInput() != null ? tcDto.getInput() : "",
                        tcDto.getExpectedOutput() != null ? tcDto.getExpectedOutput() : "",
                        idx++
                );
                problem.addTestCase(tc);
            }
        }

        Problem saved = problemRepository.save(problem);
        return toDto(saved);
    }

    public List<ProblemDto> getAllProblems(Long userId) {
        if (userId == null) {
            return problemRepository.findAll().stream()
                    .map(this::toDto)
                    .collect(Collectors.toList());
        }
        return problemRepository.findAllByUserIdOrderByIdDesc(userId).stream()
                .map(this::toDto)
                .collect(Collectors.toList());
    }

    public ProblemDto getProblem(Long id, Long userId) {
        Problem problem = problemRepository.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("문제를 찾을 수 없습니다: " + id));
        if (userId != null && problem.getUser() != null && !problem.getUser().getId().equals(userId)) {
            throw new IllegalArgumentException("해당 문제에 대한 접근 권한이 없습니다.");
        }
        return toDto(problem);
    }

    @Transactional
    public void deleteProblem(Long id, Long userId) {
        Problem problem = problemRepository.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("문제를 찾을 수 없습니다: " + id));
        if (userId != null && problem.getUser() != null && !problem.getUser().getId().equals(userId)) {
            throw new IllegalArgumentException("해당 문제에 대한 삭제 권한이 없습니다.");
        }
        problemRepository.delete(problem);
    }

    private ProblemDto toDto(Problem problem) {
        List<TestCaseDto> tcDtos = new ArrayList<>();
        if (problem.getTestCases() != null) {
            tcDtos = problem.getTestCases().stream()
                    .map(tc -> new TestCaseDto(tc.getInputData(), tc.getExpectedOutput()))
                    .collect(Collectors.toList());
        }
        return new ProblemDto(
                problem.getId(),
                problem.getTitle(),
                problem.getDescription(),
                problem.getCode(),
                problem.getTimeLimitMs(),
                problem.getMemoryLimitMb(),
                tcDtos
        );
    }
}
