import os
import tempfile
import requests
import json
import subprocess
import re
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from paddleocr import PaddleOCR

app = FastAPI(title="Judge AI Server")

# Allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize PaddleOCR (downloads models on first run)
# use_angle_cls=True to automatically rotate images if needed
# lang='korean' supports both Korean and English
ocr = PaddleOCR(use_angle_cls=True, lang='korean')

# Ollama Host (Docker service name)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434/api/generate")
MODEL_NAME = "qwen2.5:7b" # Or llama3

class HintRequest(BaseModel):
    problem_text: str
    failed_code: str

class TestcaseRequest(BaseModel):
    problem_text: str

class EdgeCaseRequest(BaseModel):
    problem_text: str

def call_ollama(prompt: str, format_json: bool = False) -> str:
    """Helper function to call local Ollama API."""
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }
    if format_json:
        payload["format"] = "json"
        
    try:
        response = requests.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        return response.json().get("response", "")
    except requests.exceptions.RequestException as e:
        print(f"Ollama API Error: {e}")
        return "Error connecting to local AI model. Ensure Ollama is running."

@app.post("/api/ai/process-problem")
async def process_problem(file: UploadFile = File(...)):
    """
    1. Runs OCR on uploaded image.
    2. Uses Ollama to format the problem and generate 10 test cases.
    """
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image.")

    # Save image to temp file for PaddleOCR
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_img:
        content = await file.read()
        temp_img.write(content)
        temp_img_path = temp_img.name

    try:
        # 1. OCR Extraction
        result = ocr.ocr(temp_img_path, cls=True)
        raw_text = ""
        if result and result[0]:
            for line in result[0]:
                text = line[1][0]
                raw_text += text + "\n"
        
        if not raw_text.strip():
            return {"error": "No text detected in the image."}

        # 2. Problem Formatting & Test Case Generation via LLM
        prompt = f"""
다음은 알고리즘 문제지 이미지를 OCR로 스캔한 거친 텍스트입니다.
이 텍스트를 바탕으로 두 가지 작업을 수행해주세요:

1. [문제 정보 정리] 제목, 문제 내용, 입력 조건, 출력 조건, 제한 사항을 깔끔한 마크다운으로 정리해주세요.
2. [테스트 케이스 생성] 위 조건들을 만족하면서, 경계값(Edge Case)을 포함하여 가장 까다롭고 틀리기 쉬운 테스트 케이스 10개를 "입력"과 "기대 출력" 형태로 만들어주세요.

**[주의: 반드시 한국어(Korean)로만 대답하세요. 절대 중국어나 영어를 사용하지 마세요.]**

--- OCR 텍스트 ---
{raw_text}
"""
        llm_response = call_ollama(prompt)
        
        return {
            "raw_ocr_text": raw_text,
            "ai_processed_result": llm_response
        }

    finally:
        if os.path.exists(temp_img_path):
            os.remove(temp_img_path)

@app.post("/api/ai/testcase")
async def generate_testcase(request: TestcaseRequest):
    """
    Analyzes problem text and generates exactly 1 edge test case in JSON format.
    """
    prompt = f"""
당신은 엄격한 알고리즘 저지(Judge) 시스템의 테스트 케이스 생성기입니다.
다음 문제 설명을 읽고, 가장 까다로운 엣지 케이스(Edge Case) 1개를 생성하세요.

문제 내용:
{request.problem_text}

반드시 아래 JSON 형식으로만 답변하세요. 다른 설명이나 마크다운은 절대 포함하지 마세요.
{{
  "input": "여기에 입력값을 문자열로 작성",
  "expected_output": "여기에 기대되는 출력값을 문자열로 작성"
}}
"""
    response = call_ollama(prompt, format_json=True)
    try:
        # Validate that it is actually parsable JSON
        parsed = json.loads(response)
        return parsed
    except json.JSONDecodeError:
        # Fallback if the model didn't return perfect JSON
        import re
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                return parsed
            except:
                pass
        raise HTTPException(status_code=500, detail="Failed to parse AI generated testcase.")

@app.post("/api/ai/testcases")
async def generate_testcases(request: TestcaseRequest):
    """
    Analyzes problem text and generates exactly 5 edge test cases in JSON object format.
    Guarantees returning 5 test cases even if LLM generates fewer.
    """
    prompt = f"""
당신은 엄격한 알고리즘 저지(Judge) 시스템의 테스트 케이스 생성기입니다.
다음 문제 설명을 읽고, 가장 까다롭고 틀리기 쉬운 엣지 케이스(Edge Case)를 포함하여 정확히 5개의 서로 다른 테스트 케이스를 생성하세요.

문제 내용:
{request.problem_text}

반드시 아래 JSON 객체(Object) 형식으로만 답변하세요. "testcases" 배열 안에 정확히 5개의 테스트 케이스를 작성해야 합니다. 다른 설명이나 마크다운은 절대 포함하지 마세요.
{{
  "testcases": [
    {{
      "input": "첫번째 입력값 문자열 (예: 10 20\\n)",
      "expected_output": "첫번째 기대 출력값 문자열 (예: 30)"
    }},
    {{
      "input": "두번째 입력값 문자열",
      "expected_output": "두번째 기대 출력값 문자열"
    }},
    {{
      "input": "세번째 입력값 문자열",
      "expected_output": "세번째 기대 출력값 문자열"
    }},
    {{
      "input": "네번째 입력값 문자열",
      "expected_output": "네번째 기대 출력값 문자열"
    }},
    {{
      "input": "다섯번째 입력값 문자열",
      "expected_output": "다섯번째 기대 출력값 문자열"
    }}
  ]
}}
"""
    response = call_ollama(prompt, format_json=True)
    print(f"Ollama raw response for testcases: {response}")
    
    fallback_extras = [
        {"input": "10 20\n", "expected_output": "30"},
        {"input": "0 0\n", "expected_output": "0"},
        {"input": "-5 5\n", "expected_output": "0"},
        {"input": "100 200\n", "expected_output": "300"},
        {"input": "999 1\n", "expected_output": "1000"}
    ]
    
    tc_list = []
    try:
        parsed = json.loads(response)
        if isinstance(parsed, list):
            tc_list = parsed
        elif isinstance(parsed, dict) and "testcases" in parsed and isinstance(parsed["testcases"], list):
            tc_list = parsed["testcases"]
        elif isinstance(parsed, dict) and "input" in parsed:
            tc_list = [parsed]
    except Exception as e:
        print(f"Failed direct JSON parse: {e}")
        import re
        match_obj = re.search(r'\{.*\}', response, re.DOTALL)
        match_arr = re.search(r'\[.*\]', response, re.DOTALL)
        if match_obj:
            try:
                parsed = json.loads(match_obj.group(0))
                if "testcases" in parsed and isinstance(parsed["testcases"], list):
                    tc_list = parsed["testcases"]
            except:
                pass
        if not tc_list and match_arr:
            try:
                parsed = json.loads(match_arr.group(0))
                if isinstance(parsed, list):
                    tc_list = parsed
            except:
                pass

    # Guarantee exactly 5 testcases
    while len(tc_list) < 5:
        tc_list.append(fallback_extras[len(tc_list) % len(fallback_extras)])
        
    return {"testcases": tc_list[:5]}

@app.post("/api/ai/hint")
async def get_hint(request: HintRequest):
    """
    Analyzes failed code and provides a hint based on time/space complexity.
    """
    prompt = f"""
당신은 최고의 알고리즘 코딩 테스트 선생님입니다.
학생이 아래 문제를 풀다가 코드가 틀렸거나 시간 초과가 발생했습니다.
정답 코드를 절대 직접 알려주지 말고, 시간 복잡도와 공간 복잡도를 분석하여 어떤 논리적 오류가 있는지 핵심적인 '힌트'만 마크다운으로 제공해주세요.

**[주의: 반드시 한국어(Korean)로만 대답하세요. 절대 중국어나 영어를 사용하지 마세요.]**

--- 문제 정보 ---
{request.problem_text}

--- 학생의 틀린 코드 ---
{request.failed_code}
"""
    hint = call_ollama(prompt)
    return {"hint": hint}

EDGE_CASE_SYSTEM_PROMPT = (
    "당신은 알고리즘 채점 서버의 엣지 케이스 및 반례 설계 전문가입니다.\n"
    "주어진 문제 설명을 분석하여 치명적인 엣지 케이스(반례)를 생성하세요.\n"
    "[생성 규칙 - 엄수!]\n"
    "1. [가장 중요] 'generator_code' 항목에는 오직 파이썬으로 `eval()` 가능한 문자열 생성 코드(Python Expression)만 적으세요.\n"
    "2. [언어 제한] 절대 중국어(Chinese)나 한자를 사용하지 마세요! 'reason'과 'case_name'은 반드시 100% 순수 한국어로만 작성하세요.\n"
    "3. [형식 엄수] 문제의 **입력 형식(Input Format)**을 글자 하나까지 완벽하게 지켜야 합니다. 줄바꿈(\\n)과 띄어쓰기를 정확히 맞춰서 생성 코드를 작성하세요. (예: 문제에서 A와 B 두 개의 변수를 요구하면 반드시 값이 2개여야 합니다. 절대 누락시키지 마세요!)\n"
    "4. 제한 조건(입력값의 범위, 개수 등)을 위반하지 않는 선에서 최대값, 최소값, 극단적 상황, 오답을 유발할 수 있는 데이터를 포함하세요.\n"
    "5. 반드시 다음과 같은 JSON 배열 구조로 응답해야 합니다:\n"
    "[\n"
    "  {\n"
    "    \"case_name\": \"유형 이름 (한국어)\",\n"
    "    \"generator_code\": \"파이썬 문자열 수식\",\n"
    "    \"reason\": \"이유 설명 (한국어)\"\n"
    "  }\n"
    "]"
)

def call_coder_ai(problem_text: str, error_feedback: str = None, previous_code: str = None, failed_input: str = None) -> str:
    chat_url = OLLAMA_URL.replace("/api/generate", "/api/chat")
    
    if not error_feedback:
        system_prompt = (
            "당신은 알고리즘 전문가입니다. 주어진 문제의 제약 조건을 완벽하게 준수하는 최적의 파이썬 정답 코드를 작성하세요.\n"
            "[중요 조건 1] 입력값이 어떤 형태로 들어오든 절대 에러가 나지 않도록, 반드시 `import sys; data = sys.stdin.read().split()` 패턴을 사용하여 입력을 파싱하세요. `input()`은 절대 금지!\n"
            "[중요 조건 2] 문법 에러(SyntaxError)를 방지하기 위해 복잡한 List Comprehension이나 한 줄 코딩(One-liner)을 피하고, 직관적이고 안전한 문법(for, if-else)을 사용하세요.\n"
            "어떤 부가 설명도 없이 오직 ```python ... ``` 블록으로만 대답하세요."
        )
        user_prompt = problem_text
    else:
        system_prompt = (
            "당신은 파이썬 디버깅 전문가입니다. 에러 로그를 분석하여 논리적/문법적 오류를 완벽히 수정한 파이썬 코드를 작성하세요.\n"
            "[중요 조건 1] 입력 에러(ValueError, EOFError)라면, 입력 포맷이 꼬인 것이므로 반드시 `import sys; data = sys.stdin.read().split()`을 사용하여 입력 로직을 전면 수정하세요.\n"
            "[중요 조건 2] 문법 에러(SyntaxError)라면, 괄호 쌍이 틀렸거나 너무 복잡한 로직이 원인이니, 로직을 쪼개어 가장 기본적이고 안전한 구문(for, if)으로 풀어서 다시 작성하세요.\n"
            "어떤 부가 설명도 없이 오직 ```python ... ``` 블록으로만 대답하세요."
        )
        user_prompt = f"[이전 코드]\n{previous_code}\n\n[실패한 입력값]\n{failed_input}\n\n[발생한 에러(Traceback)]\n{error_feedback}\n\n위 에러를 해결하여 작동하는 최종 파이썬 코드를 작성해주세요."

    payload = {
        "model": "code-generator-ai",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "stream": False
    }
    
    try:
        response = requests.post(chat_url, json=payload, timeout=60)
        response.raise_for_status()
        content = response.json().get("message", {}).get("content", "")
        
        match = re.search(r'```python\n(.*?)\n```', content, re.DOTALL)
        if match:
            return match.group(1).strip()
        else:
            return content.replace('```python', '').replace('```', '').strip()
    except Exception as e:
        print(f"Coder AI Error: {e}")
        return ""

def call_ollama_edge_case(problem_text: str) -> list:
    chat_url = OLLAMA_URL.replace("/api/generate", "/api/chat")
    user_prompt = problem_text
    
    max_retries = 5
    for attempt in range(max_retries):
        payload = {
            "model": "edge-case-ai",
            "messages": [
                {"role": "system", "content": EDGE_CASE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False
        }
        
        try:
            response = requests.post(chat_url, json=payload, timeout=60)
            response.raise_for_status()
            content = response.json().get("message", {}).get("content", "")
            
            if re.search(r'[\u4e00-\u9fff]', content):
                print(f"Edge Case Gen: Attempt {attempt+1} contained Chinese. Retrying...")
                continue
                
            clean_json = content.replace('```json', '').replace('```', '').strip()
            start_idx = clean_json.find('[')
            end_idx = clean_json.rfind(']')
            if start_idx != -1 and end_idx != -1:
                clean_json = clean_json[start_idx:end_idx+1]
            
            return json.loads(clean_json)
        except Exception as e:
            print(f"Edge Case Gen Error: {e}")
            if attempt == max_retries - 1:
                return []
    return []

@app.post("/api/ai/edge-cases")
async def generate_full_edge_cases(request: EdgeCaseRequest):
    """
    1. Coder AI generates initial python solution.
    2. Tester AI generates test cases (generator_code).
    3. Controller evaluates them. If the solution crashes, loops back to Coder AI.
    """
    # 1. 초기 반례 생성 (Tester AI)
    print("Agent: Requesting edge cases from Tester AI...")
    ai_cases = call_ollama_edge_case(request.problem_text)
    if not ai_cases:
        raise HTTPException(status_code=500, detail="Failed to generate valid JSON testcases.")

    # 2. 초기 코드 생성 (Coder AI)
    print("Agent: Requesting initial solution from Coder AI...")
    solution_code = call_coder_ai(request.problem_text)
    if not solution_code:
        raise HTTPException(status_code=500, detail="Failed to generate python code.")
    
    max_agent_retries = 3
    final_testcases = []
    
    for attempt in range(max_agent_retries):
        print(f"Agent Loop: Testing Coder's code (Attempt {attempt+1}/{max_agent_retries})")
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(solution_code)
            solution_script_path = f.name
            
        code_failed = False
        failed_error = ""
        failed_input = ""
        successful_cases = []
        
        try:
            for idx, case in enumerate(ai_cases):
                gen_code = case.get("generator_code", "")
                if not gen_code:
                    continue
                    
                # Evaluate input
                try:
                    actual_input = eval(gen_code)
                    if not isinstance(actual_input, str):
                        actual_input = str(actual_input)
                except Exception as e:
                    # eval 실패 시: 반례 생성 오류이므로 그냥 건너뜁니다 (안전성을 위해 Coder 탓은 안함)
                    print(f"Tester AI failed to create valid python expression: {e}")
                    continue
                    
                # Run subprocess
                try:
                    proc = subprocess.run(
                        ["python", solution_script_path],
                        input=actual_input,
                        capture_output=True,
                        text=True,
                        timeout=5.0
                    )
                    
                    if proc.returncode == 0:
                        successful_cases.append({
                            "case_name": case.get("case_name", f"Edge Case {idx+1}"),
                            "reason": case.get("reason", ""),
                            "input": actual_input,
                            "expected_output": proc.stdout.strip()
                        })
                    else:
                        code_failed = True
                        failed_error = proc.stderr
                        failed_input = actual_input
                        break
                        
                except subprocess.TimeoutExpired:
                    code_failed = True
                    failed_error = "TimeoutExpired: The code took longer than 5.0 seconds. It might have an infinite loop or an inefficient algorithm (e.g., O(N^2) instead of O(N log N))."
                    failed_input = actual_input
                    break
                    
            if not code_failed:
                # 완벽하게 통과함!
                final_testcases = successful_cases
                break
            else:
                # 에러 발생! 자가 치유 피드백 루프 진입
                print(f"Agent: Coder AI code failed. Requesting self-healing... Error: {failed_error[:100]}")
                if attempt < max_agent_retries - 1:
                    solution_code = call_coder_ai(
                        problem_text=request.problem_text,
                        error_feedback=failed_error,
                        previous_code=solution_code,
                        failed_input=failed_input
                    )
                    if not solution_code:
                        break # Failed to get fixed code
                        
        finally:
            if os.path.exists(solution_script_path):
                os.remove(solution_script_path)
                
    if not final_testcases:
        # 에이전트 루프가 끝났는데도 복구에 실패한 경우
        raise HTTPException(status_code=500, detail="Multi-Agent loop failed to generate valid code and testcases.")
        
    return {
        "solution_code": solution_code,
        "testcases": final_testcases
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
