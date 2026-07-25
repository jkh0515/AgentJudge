package com.vacation.judge.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.vacation.judge.config.RabbitMQConfig;
import com.vacation.judge.domain.Problem;
import com.vacation.judge.domain.Submission;
import com.vacation.judge.domain.User;
import com.vacation.judge.dto.SubmissionMessageDto;
import com.vacation.judge.dto.SubmissionRequestDto;
import com.vacation.judge.repository.ProblemRepository;
import com.vacation.judge.repository.SubmissionRepository;
import com.vacation.judge.repository.UserRepository;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.data.redis.connection.Message;
import org.springframework.data.redis.connection.MessageListener;
import org.springframework.data.redis.listener.ChannelTopic;
import org.springframework.data.redis.listener.RedisMessageListenerContainer;
import org.springframework.stereotype.Service;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Slf4j
@Service
@RequiredArgsConstructor
public class SubmissionService implements MessageListener {

    private final SubmissionRepository submissionRepository;
    private final UserRepository userRepository;
    @Value("${app.ai-server.url}")
    private String aiServerUrl;
    private final ProblemRepository problemRepository;
    private final RabbitTemplate rabbitTemplate;
    private final RedisMessageListenerContainer redisMessageListenerContainer;
    private final ObjectMapper objectMapper;

    private final Map<Long, SseEmitter> emitters = new ConcurrentHashMap<>();

    @PostConstruct
    public void init() {
        redisMessageListenerContainer.addMessageListener(this, new ChannelTopic("judge_events"));
    }

    @Transactional
    public Long submitCode(SubmissionRequestDto requestDto) {
        User user = userRepository.findById(requestDto.getUserId())
                .orElseThrow(() -> new IllegalArgumentException("User not found"));

        Submission submission = new Submission(user, requestDto.getProblemText(), requestDto.getCode(), requestDto.getLanguage());

        java.util.List<com.vacation.judge.dto.TestCaseDto> testCases = requestDto.getTestCases();
        if (testCases == null || testCases.isEmpty()) {
            testCases = java.util.List.of(new com.vacation.judge.dto.TestCaseDto("10 10\n", "20"));
        }
        try {
            submission.setTestCasesJson(objectMapper.writeValueAsString(testCases));
        } catch (Exception e) {
            log.error("Failed to serialize testCases", e);
        }
        submissionRepository.save(submission);
        String firstInput = testCases.get(0).getInput();
        String firstExpected = testCases.get(0).getExpectedOutput();

        SubmissionMessageDto messageDto = new SubmissionMessageDto(
                submission.getId(),
                submission.getCode(),
                submission.getLanguage(),
                firstInput,
                firstExpected,
                2,
                testCases
        );

        rabbitTemplate.convertAndSend(RabbitMQConfig.QUEUE_NAME, messageDto);
        log.info("Published submission {} with {} testcases to RabbitMQ", submission.getId(), testCases.size());

        return submission.getId();
    }

    public SseEmitter subscribe(Long submissionId) {
        SseEmitter emitter = new SseEmitter(60 * 1000L); // 60 seconds timeout
        emitters.put(submissionId, emitter);

        emitter.onCompletion(() -> emitters.remove(submissionId));
        emitter.onTimeout(() -> emitters.remove(submissionId));
        emitter.onError((e) -> emitters.remove(submissionId));

        try {
            emitter.send(SseEmitter.event().name("connect").data("Connected to submission " + submissionId));
            
            // Check if submission is already processed to prevent race condition
            submissionRepository.findById(submissionId).ifPresent(submission -> {
                if (submission.getStatus() != null && !submission.getStatus().equals("PENDING") && !submission.getStatus().equals("READY")) {
                    try {
                        String body = objectMapper.writeValueAsString(Map.of(
                                "submission_id", submission.getId(),
                                "status", submission.getStatus(),
                                "output", submission.getResultOutput() != null ? submission.getResultOutput() : ""
                        ));
                        emitter.send(SseEmitter.event().name("judge_result").data(body));
                        emitter.complete();
                    } catch (IOException e) {
                        log.error("Failed to send immediate result", e);
                    }
                }
            });
            
        } catch (IOException e) {
            emitters.remove(submissionId);
        }

        return emitter;
    }

    @Override
    @Transactional
    public void onMessage(Message message, byte[] pattern) {
        try {
            String body = new String(message.getBody());
            log.info("Received message from Redis: {}", body);
            JsonNode jsonNode = objectMapper.readTree(body);

            Long submissionId = jsonNode.get("submission_id").asLong();
            String type = jsonNode.has("type") ? jsonNode.get("type").asText() : "SUBMISSION_COMPLETE";

            SseEmitter emitter = emitters.get(submissionId);

            if ("TESTCASE_RESULT".equals(type)) {
                if (emitter != null) {
                    emitter.send(SseEmitter.event().name("testcase_result").data(body));
                }
            } else {
                String status = jsonNode.has("status") ? jsonNode.get("status").asText() : "FAIL";
                String output = jsonNode.has("output") ? jsonNode.get("output").asText() : "";

                // Update DB
                submissionRepository.findById(submissionId).ifPresent(submission -> {
                    submission.setStatus(status);
                    submission.setResultOutput(output);
                    submissionRepository.save(submission);
                });

                if (emitter != null) {
                    emitter.send(SseEmitter.event().name("judge_result").data(body));
                    emitter.complete();
                }
            }
        } catch (Exception e) {
            log.error("Error processing redis message", e);
        }
    }
}
