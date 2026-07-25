package com.vacation.judge.controller;

import com.vacation.judge.dto.ProblemCreateRequestDto;
import com.vacation.judge.dto.ProblemDto;
import com.vacation.judge.service.ProblemService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/problems")
@RequiredArgsConstructor
public class ProblemController {

    private final ProblemService problemService;

    private Long getUserId(Authentication authentication) {
        if (authentication != null && authentication.isAuthenticated() && 
            authentication.getPrincipal() instanceof com.vacation.judge.security.CustomUserDetails) {
            com.vacation.judge.security.CustomUserDetails userDetails = (com.vacation.judge.security.CustomUserDetails) authentication.getPrincipal();
            return userDetails.getUser().getId();
        }
        return null;
    }

    @PostMapping
    public ResponseEntity<?> createProblem(@RequestBody ProblemCreateRequestDto request, Authentication authentication) {
        try {
            Long userId = getUserId(authentication);
            ProblemDto saved = problemService.saveProblem(request, userId);
            return ResponseEntity.ok(saved);
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(Map.of("error", e.getMessage()));
        }
    }

    @GetMapping
    public ResponseEntity<List<ProblemDto>> getAllProblems(Authentication authentication) {
        Long userId = getUserId(authentication);
        return ResponseEntity.ok(problemService.getAllProblems(userId));
    }

    @GetMapping("/{id}")
    public ResponseEntity<?> getProblem(@PathVariable Long id, Authentication authentication) {
        try {
            Long userId = getUserId(authentication);
            ProblemDto problem = problemService.getProblem(id, userId);
            return ResponseEntity.ok(problem);
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(Map.of("error", e.getMessage()));
        }
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<?> deleteProblem(@PathVariable Long id, Authentication authentication) {
        try {
            Long userId = getUserId(authentication);
            problemService.deleteProblem(id, userId);
            return ResponseEntity.ok(Map.of("message", "삭제되었습니다."));
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(Map.of("error", e.getMessage()));
        }
    }
}
