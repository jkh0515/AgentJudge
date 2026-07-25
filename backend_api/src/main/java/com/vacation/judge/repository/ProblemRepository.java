package com.vacation.judge.repository;

import com.vacation.judge.domain.Problem;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;
import java.util.Optional;

public interface ProblemRepository extends JpaRepository<Problem, Long> {
    List<Problem> findAllByUserIdOrderByIdDesc(Long userId);
    Optional<Problem> findByIdAndUserId(Long id, Long userId);
}
