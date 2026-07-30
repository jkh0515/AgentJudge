package com.vacation.judge.controller;

import com.vacation.judge.dto.AiHintRequestDto;
import com.vacation.judge.service.AiService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.web.client.RestTemplate;
import org.springframework.core.io.Resource;

import java.util.Map;

@RestController
@RequestMapping("/api/ai")
@RequiredArgsConstructor
public class AiController {

    private final AiService aiService;
    private final RestTemplate restTemplate = new RestTemplate();

    @Value("${app.ai-server.url}")
    private String aiServerBaseUrl;

    @PostMapping("/process-problem")
    public ResponseEntity<?> processProblem(@RequestParam("file") MultipartFile file) {
        try {
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.MULTIPART_FORM_DATA);
            
            MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
            body.add("file", file.getResource());
            
            HttpEntity<MultiValueMap<String, Object>> requestEntity = new HttpEntity<>(body, headers);
            
            String aiServerUrl = aiServerBaseUrl + "/process-problem";
            ResponseEntity<Map> response = restTemplate.postForEntity(aiServerUrl, requestEntity, Map.class);
            
            return ResponseEntity.ok(response.getBody());
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(Map.of("error", e.getMessage()));
        }
    }

    @PostMapping("/hint")
    public ResponseEntity<?> getHint(@RequestBody AiHintRequestDto request) {
        try {
            String hint = aiService.getHint(request);
            return ResponseEntity.ok(Map.of("hint", hint));
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(Map.of("error", e.getMessage()));
        }
    }

    @PostMapping("/testcases")
    public ResponseEntity<?> generateTestcases(@RequestBody Map<String, String> request) {
        try {
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            
            HttpEntity<Map<String, String>> entity = new HttpEntity<>(request, headers);
            // AI 서버의 최신 Multi-Agent (Self-Healing) 엔드포인트로 라우팅
            String aiServerUrl = aiServerBaseUrl + "/edge-cases";
            
            ResponseEntity<Map> response = restTemplate.postForEntity(aiServerUrl, entity, Map.class);
            return ResponseEntity.ok(response.getBody());
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(Map.of("error", e.getMessage()));
        }
    }
}
