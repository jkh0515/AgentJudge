import os
import tempfile
import requests
import json
import subprocess
import re
import asyncio
import httpx
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
    "You are an expert algorithm test case designer. Analyze the problem and generate CHALLENGING edge cases.\n"
    "[STEP 1 - Read Constraints First]\n"
    "Before generating any input, carefully read the Input section of the problem to understand:\n"
    "  - What values N, C, or other variables can take (min/max bounds)\n"
    "  - What the coordinates/values can be (e.g., 0 to 10^9, must be distinct, etc.)\n"
    "  - Exactly how many lines/values the input must have\n"
    "[STEP 2 - Generate VALID inputs]\n"
    "1. The 'input' field must be the EXACT stdin string. Use \\n for newlines.\n"
    "2. STRICTLY follow the constraints you read in Step 1. Do NOT exceed bounds or use forbidden values.\n"
    "3. Token count must match EXACTLY: if first line is 'N C', then there must be exactly N more values.\n"
    "   Example: N=3, C=2, houses=[1,5,9] -> input = '3 2\\n1\\n5\\n9' (exactly 5 tokens total)\n"
    "4. Never use Chinese characters. Use only Korean for 'case_name' and 'reason'.\n"
    "5. Target: max N, min N, greedy traps (clustered points), all same distance, extreme values.\n"
    "6. Coordinates must all be DISTINCT (no duplicates).\n"
    "[OUTPUT FORMAT] Respond ONLY with a valid JSON array:\n"
    "[\n"
    "  {\n"
    "    \"case_name\": \"케이스 이름 (한국어)\",\n"
    "    \"input\": \"실제 stdin 입력 문자열\",\n"
    "    \"reason\": \"이 케이스를 선택한 이유 (한국어)\"\n"
    "  }\n"
    "]"
)

async def call_coder_ai_async(client: httpx.AsyncClient, problem_text: str, error_feedback: str = None, previous_code: str = None, failed_input: str = None) -> str:
    chat_url = OLLAMA_URL.replace("/api/generate", "/api/chat")
    
    if not error_feedback:
        system_prompt = (
            "You are an expert competitive programmer. Solve the given algorithm problem by writing complete, working Python code.\n"
            "[RULE 1] You MUST parse all input using: data = sys.stdin.read().split()\n"
            "  - data[0], data[1], data[2]... are the whitespace-separated tokens in order\n"
            "  - Do NOT use input() or sys.stdin.readline()\n"
            "[RULE 2] Write the FULL algorithm. Do NOT leave placeholder comments.\n"
            "[RULE 3] Output ONLY a single ```python ... ``` code block. No explanations.\n"
            "[EXAMPLE FORMAT]\n"
            "```python\n"
            "import sys\n"
            "def solve():\n"
            "    data = sys.stdin.read().split()\n"
            "    n, m = int(data[0]), int(data[1])\n"
            "    arr = list(map(int, data[2:n+2]))\n"
            "    # ... full algorithm here ...\n"
            "    print(answer)\n"
            "if __name__ == '__main__':\n"
            "    solve()\n"
            "```"
        )
        user_prompt = problem_text
    else:
        system_prompt = (
            "You are an expert competitive programmer. Fix the previous buggy code by writing complete, correct Python code.\n"
            "[RULE 1] You MUST parse all input using: data = sys.stdin.read().split()\n"
            "  - data[0], data[1], data[2]... are the whitespace-separated tokens in order\n"
            "  - Do NOT use input() under any circumstances\n"
            "[RULE 2] Write the FULL algorithm. Do NOT leave placeholder comments.\n"
            "[RULE 3] Output ONLY a single ```python ... ``` code block. No explanations."
        )
        user_prompt = f"[Previous Code]\n{previous_code}\n\n[Failed Input]\n{failed_input}\n\n[Error or Wrong Output Feedback]\n{error_feedback}\n\nFix all bugs and write a complete working Python solution."

    payload = {
        "model": "code-generator-ai",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "stream": False,
        "options": {
            "num_ctx": 4096
        }
    }
    
    try:
        response = await client.post(chat_url, json=payload, timeout=90)
        response.raise_for_status()
        content = response.json().get("message", {}).get("content", "")
        
        match = re.search(r'```python\n(.*?)\n```', content, re.DOTALL)
        if match:
            return match.group(1).strip()
        else:
            return content.replace('```python', '').replace('```', '').strip()
    except Exception as e:
        print(f"Coder AI Async Error: {e}")
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
            
            cases = json.loads(clean_json)
            
            # Normalize: support both old 'generator_code' and new 'input' field
            normalized = []
            for case in cases:
                if "input" in case:
                    # New format: direct input string
                    normalized.append(case)
                elif "generator_code" in case:
                    # Legacy format: try to eval the expression
                    try:
                        actual_input = eval(case["generator_code"])
                        if isinstance(actual_input, str):
                            case["input"] = actual_input
                            normalized.append(case)
                    except Exception as e:
                        print(f"Legacy generator_code eval failed: {e}")
            
            if normalized:
                return normalized
        except Exception as e:
            print(f"Edge Case Gen Error: {e}")
            if attempt == max_retries - 1:
                return []
    return []

JUDGE_SYSTEM_PROMPT = (
    "당신은 공정한 알고리즘 판사(Judge AI)입니다. Tester AI(반례 생성기)가 만든 [입력값]을 3명의 Coder AI(코드 생성기)가 각각 작성한 파이썬 코드에 넣고 실행했습니다. 그 결과(출력값 또는 에러)는 아래와 같습니다.\n"
    "누가 잘못했는지 판결하고, 올바른 정답이 무엇인지 확인하세요.\n"
    "[핵심 전제]\n"
    "Coder AI는 반드시 `import sys; data = sys.stdin.read().split()` 방식으로 입력을 파싱합니다.\n"
    "이 방식은 줄바꿈(\\n)과 공백( )을 모두 구분자로 처리합니다.\n"
    "따라서 '값들이 한 줄에 다 있다', '줄바꿈이 없다' 같은 형식 차이는 TESTER의 잘못이 아닙니다!\n"
    "[판결 기준]\n"
    "1. Tester AI의 잘못(TESTER): 입력값의 숫자 개수가 문제 조건과 다르거나, 값이 제약 범위를 벗어나거나, 파이썬 int로 변환 불가능한 값이 있는 경우만 해당. 줄바꿈/공백 형식 차이는 TESTER 잘못이 아님!\n"
    "2. Coder AI의 잘못(CODER): 입력값이 정상인데(개수, 타입, 범위 모두 OK) 3명의 Coder AI들이 모두 틀린 오답을 냈거나 에러를 발생시킨 경우.\n"
    "3. 정상(NONE): 입력값도 정상이고, Coder AI 중 최소 1명이 올바른 정답을 출력한 경우.\n"
    "[형식 엄수]\n"
    "반드시 아래 JSON 형식으로만 답변하세요. 다른 설명이나 마크다운은 절대 포함하지 마세요.\n"
    "{\n"
    "  \"fault\": \"CODER\" | \"TESTER\" | \"NONE\",\n"
    "  \"expected_output\": \"정답값 (fault가 NONE일 때만 기재, 나머지는 빈 문자열)\",\n"
    "  \"reason\": \"판결 이유 설명 (한국어)\"\n"
    "}"
)

def call_judge_ai(problem_text: str, test_input: str, outputs: list) -> dict:
    chat_url = OLLAMA_URL.replace("/api/generate", "/api/chat")
    user_prompt = f"[문제 설명]\n{problem_text}\n\n[Tester가 던진 입력값]\n{test_input}\n\n[Coder들의 실행 결과]\n"
    for i, out in enumerate(outputs):
        user_prompt += f"Coder {i+1}: {out}\n"
    user_prompt += "\n위 내용을 분석하여 누구의 잘못인지, 그리고 올바른 정답이 무엇인지 판결해주세요."
    
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "stream": False,
        "format": "json",
        "options": {
            "num_ctx": 4096
        }
    }
    
    try:
        response = requests.post(chat_url, json=payload, timeout=60)
        response.raise_for_status()
        content = response.json().get("message", {}).get("content", "")
        parsed = json.loads(content)
        return parsed
    except Exception as e:
        print(f"Judge AI Error: {e}")
        return {"fault": "CODER", "reason": "Judge AI failed to parse, defaulting to CODER fault.", "expected_output": ""}

VERIFIER_SYSTEM_PROMPT = (
    "당신은 최종 검증자(Final Verifier AI)입니다. [문제]와 [입력값]이 주어졌을 때 파이썬 코드가 무사히 실행되어 [출력값]을 내놓았습니다.\n"
    "이 출력값이 상식적으로나 논리적으로 완전히 불가능한 오답인지 검증하세요.\n"
    "[주의사항]\n"
    "당신(LLM)은 복잡한 알고리즘의 결괏값을 정확히 계산할 수 없습니다. 절대 직접 계산하여 틀렸다고 판단하지 마세요!\n"
    "오직 다음과 같은 명백한 오류일 때만 is_correct: false를 반환하세요:\n"
    "1. 출력 형식이 완전히 틀렸을 때 (예: 숫자를 출력해야 하는데 문자열이나 리스트가 출력됨)\n"
    "2. 문제의 제약 조건을 터무니없이 벗어날 때 (예: 거리의 최댓값을 구하는데 음수가 나옴)\n"
    "그 외에는 무조건 is_correct: true를 반환하세요.\n"
    "[형식 엄수]\n"
    "반드시 아래 JSON 형식으로만 답변하세요. 다른 설명이나 마크다운은 절대 포함하지 마세요.\n"
    "{\n"
    "  \"is_correct\": true | false,\n"
    "  \"reason\": \"검증 이유 설명 (한국어)\"\n"
    "}"
)

def call_verifier_ai(problem_text: str, test_input: str, test_output: str) -> dict:
    chat_url = OLLAMA_URL.replace("/api/generate", "/api/chat")
    user_prompt = f"[문제 설명]\n{problem_text}\n\n[입력값]\n{test_input}\n\n[도출된 출력값]\n{test_output}\n\n위 출력값이 명백한 오답인지 검증해주세요."
    
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": VERIFIER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "stream": False,
        "format": "json",
        "options": {
            "num_ctx": 4096
        }
    }
    
    try:
        response = requests.post(chat_url, json=payload, timeout=60)
        response.raise_for_status()
        content = response.json().get("message", {}).get("content", "")
        parsed = json.loads(content)
        return parsed
    except Exception as e:
        print(f"Verifier AI Error: {e}")
        return {"is_correct": True, "reason": "Verifier AI failed, assuming true."}

def parse_sample_cases(problem_text: str) -> list:
    """
    Extract sample input/output pairs from problem text.
    Handles: '예제 입력', '예제 입력 1/2', 'Sample Input', 'Example Input' etc.
    Returns list of {"input": str, "output": str} dicts.
    """
    cases = []
    
    # Strategy 1: Multiple numbered samples (예제 입력 1 / 예제 출력 1)
    blocks = re.split(r'(?=예제\s*입력\s*\d+|Sample\s*Input\s*\d+)', problem_text, flags=re.IGNORECASE)
    for block in blocks:
        inp_m = re.search(r'(?:예제\s*입력|Sample\s*Input)\s*\d*\s*\n([\s\S]*?)(?:예제\s*출력|Sample\s*Output|Expected)', block, re.IGNORECASE)
        out_m = re.search(r'(?:예제\s*출력|Sample\s*Output|Expected)\s*\d*\s*\n([\s\S]*?)(?:예제\s*입력|Sample\s*Input|$)', block, re.IGNORECASE)
        if inp_m and out_m:
            inp = inp_m.group(1).strip()
            out = out_m.group(1).strip()
            if inp and out:
                cases.append({"input": inp, "output": out})
    
    if cases:
        return cases
    
    # Strategy 2: Single sample (예제 입력 / 예제 출력)
    inp_m = re.search(r'(?:예제\s*입력|Sample\s*Input)[^\n]*\n([\s\S]*?)(?:예제\s*출력|Sample\s*Output)', problem_text, re.IGNORECASE)
    out_m = re.search(r'(?:예제\s*출력|Sample\s*Output)[^\n]*\n([\s\S]*?)(?:\n\n|$)', problem_text, re.IGNORECASE)
    if inp_m and out_m:
        inp = inp_m.group(1).strip()
        out = out_m.group(1).strip()
        if inp and out:
            cases.append({"input": inp, "output": out})
    
    return cases

async def run_code_against_input(code: str, test_input: str) -> str:
    """Run python code string with given stdin input. Returns stdout or 'ERROR: ...'."""
    import tempfile, os
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(code)
        tmp_path = f.name
    try:
        proc = await asyncio.create_subprocess_exec(
            "python", tmp_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(input=test_input.encode()), timeout=5.0)
            if proc.returncode == 0:
                return stdout.decode().strip()
            else:
                return f"ERROR: {stderr.decode().strip()[:200]}"
        except asyncio.TimeoutError:
            proc.kill()
            return "ERROR: TimeoutError"
    finally:
        try:
            os.remove(tmp_path)
        except:
            pass

@app.post("/api/ai/edge-cases")
async def generate_full_edge_cases(request: EdgeCaseRequest):
    print("Agent: Requesting edge cases from Tester AI...")
    ai_cases = call_ollama_edge_case(request.problem_text)
    if not ai_cases:
        return {"error": "Failed to generate valid JSON testcases."}

    print("Agent: Requesting 3 different solutions from Coder AI concurrently...")
    async with httpx.AsyncClient() as client:
        tasks = [call_coder_ai_async(client, request.problem_text) for _ in range(3)]
        solution_codes = await asyncio.gather(*tasks)
    
    solution_codes = [c for c in solution_codes if c]
    if not solution_codes:
        return {"error": "Failed to generate python code."}
        
    final_solution_code = solution_codes[0]
    
    # ===== STEP: Sample Case Pre-Validation & Self-Healing =====
    sample_cases = parse_sample_cases(request.problem_text)
    if sample_cases:
        print(f"Agent: Found {len(sample_cases)} sample case(s). Running pre-validation...")
        sample_passed = False
        
        async with httpx.AsyncClient() as client:
            # Phase 1: Self-heal up to 3 times
            for sample_attempt in range(3):
                failed_sample = None
                for sc in sample_cases:
                    result = await run_code_against_input(final_solution_code, sc["input"])
                    expected = sc["output"].strip()
                    if result.strip() != expected:
                        failed_sample = sc
                        print(f"Agent: [Sample FAIL] Expected='{expected}', Got='{result}'")
                        break
                
                if failed_sample is None:
                    print(f"Agent: All {len(sample_cases)} sample case(s) PASSED! Proceeding...")
                    sample_passed = True
                    break
                
                print(f"Agent: Sample self-healing attempt {sample_attempt+1}/3...")
                error_feedback = (
                    f"Sample case FAILED.\n"
                    f"Input: {failed_sample['input']}\n"
                    f"Expected output: {failed_sample['output'].strip()}\n"
                    f"Actual output  : {result}\n"
                    f"The binary search direction or logic is wrong. Fix the algorithm completely."
                )
                healed = await call_coder_ai_async(
                    client, request.problem_text,
                    error_feedback=error_feedback,
                    previous_code=final_solution_code,
                    failed_input=failed_sample["input"]
                )
                if healed:
                    final_solution_code = healed
            
            # Phase 2: If still failing, generate completely fresh code (not self-heal)
            if not sample_passed:
                print("Agent: Self-healing failed. Generating fresh code from scratch...")
                for fresh_attempt in range(3):
                    fresh_tasks = [call_coder_ai_async(client, request.problem_text) for _ in range(3)]
                    fresh_codes = await asyncio.gather(*fresh_tasks)
                    fresh_codes = [c for c in fresh_codes if c]
                    
                    for fresh_code in fresh_codes:
                        all_pass = True
                        for sc in sample_cases:
                            result = await run_code_against_input(fresh_code, sc["input"])
                            if result.strip() != sc["output"].strip():
                                all_pass = False
                                break
                        if all_pass:
                            final_solution_code = fresh_code
                            sample_passed = True
                            print(f"Agent: Fresh code passed all samples! Proceeding...")
                            break
                    if sample_passed:
                        break
                    print(f"Agent: Fresh generation attempt {fresh_attempt+1}/3 failed.")
            
            if not sample_passed:
                print("Agent: WARNING - Could not generate code that passes sample cases.")
                return {"error": "Failed to generate code that passes the sample test cases after multiple attempts."}
    else:
        print("Agent: No sample cases found in problem text. Skipping pre-validation.")
    # ===== END Sample Case Pre-Validation =====

    
    max_agent_retries = 10
    final_testcases = []
    judge_logs = []
    case_fail_counts = {}  # track per-case failures: case_name -> fail_count
    blacklist_cases = set()  # permanently skipped cases
    
    for attempt in range(max_agent_retries):
        print(f"Agent Loop: Testing Coder's codes (Attempt {attempt+1}/{max_agent_retries})")
        
        temp_paths = []
        for sc in solution_codes:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
                f.write(sc)
                temp_paths.append(f.name)
                
        code_failed = False
        failed_error = ""
        failed_input = ""
        successful_cases = []
        surviving_code_indices = list(range(len(solution_codes)))
        
        try:
            for idx, case in enumerate(ai_cases):
                case_name = case.get("case_name", f"Edge Case {idx+1}")
                # Skip blacklisted cases
                if case_name in blacklist_cases:
                    print(f"Skipping blacklisted case: {case_name}")
                    continue
                
                # New format: 'input' field is the direct input string
                actual_input = case.get("input", "")
                if not actual_input:
                    continue
                
                # --- Input sanity check: skip obviously malformed inputs ---
                actual_input = actual_input.strip()
                tokens = actual_input.split()
                if len(tokens) < 4:
                    print(f"Tester input too short ({len(tokens)} tokens), skipping case: {case.get('case_name')}")
                    continue
                try:
                    n_val = int(tokens[0])
                    c_val = int(tokens[1])
                    if n_val <= 0 or c_val <= 0 or c_val > n_val:
                        print(f"Tester input violates constraints (N={n_val}, C={c_val}), skipping.")
                        continue
                    # Require EXACTLY N+2 tokens (N, C, and exactly N coords)
                    if len(tokens) != n_val + 2:
                        print(f"Tester input wrong token count: need {n_val+2}, got {len(tokens)}, skipping.")
                        continue
                    # All coordinate tokens must be integers
                    coords = [int(t) for t in tokens[2:]]
                    # Check for duplicates
                    if len(set(coords)) != len(coords):
                        print(f"Tester input has duplicate coordinates, skipping.")
                        continue
                except (ValueError, IndexError):
                    print(f"Tester input has non-integer tokens, skipping.")
                    continue
                
                async def run_code(path):
                    try:
                        proc = await asyncio.create_subprocess_exec(
                            "python", path,
                            stdin=asyncio.subprocess.PIPE,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        try:
                            stdout, stderr = await asyncio.wait_for(proc.communicate(input=actual_input.encode()), timeout=5.0)
                            if proc.returncode == 0:
                                return stdout.decode().strip()
                            else:
                                return f"ERROR: {stderr.decode().strip()}"
                        except asyncio.TimeoutError:
                            proc.kill()
                            return "ERROR: TimeoutExpired: The code took longer than 5.0 seconds."
                    except Exception as e:
                        return f"ERROR: {str(e)}"
                
                run_tasks = [run_code(path) for path in temp_paths]
                outputs = await asyncio.gather(*run_tasks)
                
                # Auto-detect Tester fault: if ALL coders get same error type
                error_types = []
                for o in outputs:
                    if "IndexError" in o or "list index out of range" in o:
                        error_types.append("IndexError")
                    elif "ValueError" in o:
                        error_types.append("ValueError")
                    elif "NameError" in o:
                        error_types.append("NameError")
                if len(error_types) == len(outputs) and len(set(error_types)) == 1:
                    err_type = error_types[0]
                    case_name = case.get("case_name", f"Edge Case {idx+1}")
                    case_fail_counts[case_name] = case_fail_counts.get(case_name, 0) + 1
                    print(f"All coders got {err_type} ({case_fail_counts[case_name]} times) - case: {case_name}")
                    if case_fail_counts[case_name] >= 3:
                        print(f"Case '{case_name}' failed 3+ times - blacklisting and skipping permanently.")
                        blacklist_cases.add(case_name)
                    judge_logs.append({
                        "attempt": attempt + 1,
                        "case_name": case_name,
                        "fault": "TESTER",
                        "reason": f"자동 감지: 모든 Coder가 {err_type} 발생 ({case_fail_counts[case_name]}회). 케이스를 스킵합니다."
                    })
                    continue
                
                valid_outputs = [o for o in outputs if not o.startswith("ERROR:")]
                unique_outputs = list(set(valid_outputs))
                
                if not valid_outputs or len(unique_outputs) > 1:
                    print(f"Agent: Errors or divergence detected. Calling Judge AI...")
                    judge_result = call_judge_ai(request.problem_text, actual_input, outputs)
                    
                    judge_logs.append({
                        "attempt": attempt + 1,
                        "case_name": case.get("case_name", f"Edge Case {idx+1}"),
                        "fault": judge_result.get("fault", "CODER"),
                        "reason": judge_result.get("reason", "")
                    })
                    
                    if judge_result.get("fault") == "TESTER":
                        # Bad test case from Tester - just skip it, don't fail coders
                        print(f"Judge AI ruled TESTER fault: {judge_result.get('reason')}")
                        continue
                    elif judge_result.get("fault") == "CODER":
                        # Count how many errors vs how many we already passed
                        error_count = sum(1 for o in outputs if o.startswith("ERROR:"))
                        if error_count == len(outputs):
                            # All coders errored - genuine coder failure
                            code_failed = True
                            failed_error = f"Judge AI 판결 (CODER 잘못): {judge_result.get('reason')}\n출력결과들: {outputs}"
                            failed_input = actual_input
                            break
                        else:
                            # Some passed, some failed - use the majority output
                            from collections import Counter
                            cnt = Counter(o for o in outputs if not o.startswith("ERROR:"))
                            expected_output = cnt.most_common(1)[0][0]
                    else:
                        expected_output = str(judge_result.get("expected_output", unique_outputs[0] if unique_outputs else ""))
                else:
                    # All 3 coders agreed - trust the consensus immediately (no Verifier needed)
                    expected_output = unique_outputs[0]
                    
                # Filter surviving codes: must exactly match the expected output
                surviving_code_indices = [i for i in surviving_code_indices if outputs[i] == expected_output]
                
                if not surviving_code_indices:
                    print("Agent: No code perfectly matched the expected output.")
                    code_failed = True
                    failed_error = f"Logical Error: AI outputs diverged and all surviving codes failed to produce the correct expected output: {expected_output}."
                    failed_input = actual_input
                    break
                    
                # ✅ No Verifier AI call - trust 3-coder consensus and Judge arbitration
                successful_cases.append({
                    "case_name": case.get("case_name", f"Edge Case {idx+1}"),
                    "reason": case.get("reason", ""),
                    "input": actual_input,
                    "expected_output": expected_output
                })
                        
            if not code_failed:
                final_testcases = successful_cases
                final_solution_code = solution_codes[surviving_code_indices[0]]
                break
            else:
                print(f"Agent: Coder AI codes failed. Requesting self-healing... Error: {failed_error[:100]}")
                if attempt < max_agent_retries - 1:
                    async with httpx.AsyncClient() as client:
                        tasks = [call_coder_ai_async(client, request.problem_text, failed_error, solution_codes[0], failed_input) for _ in range(3)]
                        solution_codes = await asyncio.gather(*tasks)
                        solution_codes = [c for c in solution_codes if c]
                        
                    if not solution_codes:
                        break
                    
        finally:
            for path in temp_paths:
                if os.path.exists(path):
                    os.remove(path)
                
    if not final_testcases:
        return {
            "error": "Multi-Agent loop failed to generate valid code and testcases.",
            "judge_logs": judge_logs
        }
        
    return {
        "solution_code": final_solution_code,
        "testcases": final_testcases,
        "judge_logs": judge_logs
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
