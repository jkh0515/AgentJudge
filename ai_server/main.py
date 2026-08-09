import os
import tempfile
import requests
import json
import subprocess
import re
import asyncio
import httpx
import cv2
import numpy as np
import ast

def robust_parse_json(text: str):
    try:
        return json.loads(text)
    except Exception:
        pass
    clean_text = text.replace('```json', '').replace('```', '').strip()
    start_arr, end_arr = clean_text.find('['), clean_text.rfind(']')
    start_obj, end_obj = clean_text.find('{'), clean_text.rfind('}')
    candidates = [clean_text]
    if start_arr != -1 and end_arr != -1 and start_arr < end_arr:
        candidates.append(clean_text[start_arr:end_arr+1])
    if start_obj != -1 and end_obj != -1 and start_obj < end_obj:
        candidates.append(clean_text[start_obj:end_obj+1])
    for cand in candidates:
        cand = cand.strip()
        if not cand: continue
        try:
            return json.loads(cand)
        except Exception:
            pass
        try:
            no_trailing = re.sub(r',\s*([\]}])', r'\1', cand)
            return json.loads(no_trailing)
        except Exception:
            pass
        try:
            python_str = cand.replace("true", "True").replace("false", "False").replace("null", "None")
            res = ast.literal_eval(python_str)
            if isinstance(res, (dict, list)):
                return res
        except Exception:
            pass
    raise ValueError("Failed to robustly parse JSON")

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from auth import verify_token
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
    answer_code: Optional[str] = None

class TestcaseRequest(BaseModel):
    problem_text: str

class EdgeCaseRequest(BaseModel):
    problem_text: str

class RefineRequest(BaseModel):
    raw_text: str

async def call_ollama(client: httpx.AsyncClient, prompt: str, format_json: bool = False, temperature: float = None) -> str:
    """Helper function to call local Ollama API asynchronously."""
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }
    if format_json:
        payload["format"] = "json"
    if temperature is not None:
        payload["options"] = {"temperature": temperature}
        
    try:
        response = await client.post(OLLAMA_URL, json=payload, timeout=60.0)
        response.raise_for_status()
        return response.json().get("response", "")
    except Exception as e:
        print(f"Ollama API Error: {e}")
        return "Error connecting to local AI model. Ensure Ollama is running."

def process_image_sync(content: bytes, temp_path: str):
    """CPU-bound image preprocessing for OCR."""
    np_arr = np.frombuffer(content, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if img is not None:
        img = cv2.resize(img, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        cv2.imencode('.png', gray)[1].tofile(temp_path)
    else:
        with open(temp_path, 'wb') as f:
            f.write(content)

async def refine_text_with_llm(raw_text: str) -> str:
    prompt = f"""
You are an expert algorithm problem writer. 
I will give you a completely broken, corrupted OCR text of a programming problem, OR a rough draft of a problem.
Your job is to COMPLETELY REWRITE it into a natural, perfect Korean algorithm problem.

You MUST wrap your final Korean text strictly inside <result> and </result> tags. DO NOT add any conversational preamble.

[RULES]
1. COMPLETELY REWRITE: Do NOT try to preserve weird alien text (like '|o롬으릉', 'Yo言', '머우어0윙', '람RYPTO', 'Ioly울'). Completely throw them away and REWRITE the sentence so it makes logical sense in Korean.
2. NATURAL FLOW: Ensure it reads perfectly smoothly as a standard Baekjoon or Programmers problem.
3. PRESERVE LOGIC: You can change the wording to fix broken sentences, but do NOT alter the math rules, variable names (N, M, t), or numbers.
4. LAYOUT FORMATTING: Add empty lines between paragraphs. ALWAYS add an empty line before sections like "문제", "입력", "출력", "예제 입력 1", "예제 출력 1".
5. FREEZE EXAMPLES: The data under "예제 입력 1" and "예제 출력 1" MUST be kept absolutely identical to the raw text. Do not format it.

<raw_text>
{raw_text}
"""
    max_retries = 7
    final_text = ""
    
    async with httpx.AsyncClient() as client:
        for attempt in range(max_retries):
            temp = 0.2 + (attempt * 0.1)
            llm_response = await call_ollama(client, prompt, temperature=temp)
            
            if re.search(r'[一-鿿]', llm_response):
                print(f"Agent: OCR Refiner attempt {attempt+1} contained Chinese. Retrying with temp {temp}...")
                continue
                
            match = re.search(r'<result>(.*?)</result>', llm_response, re.DOTALL)
            if match:
                final_text = match.group(1).strip()
                if final_text:
                    return final_text
            
            fallback_match = re.search(r'(#\s*문제.*)', llm_response, re.DOTALL | re.IGNORECASE)
            if fallback_match:
                final_text = fallback_match.group(1).strip()
                final_text = re.sub(r'\n\n(위와 같이|여기 정제된|도움이 되셨나요|Here is|Hope this helps).*$', '', final_text, flags=re.DOTALL)
                if final_text:
                    print(f"Agent: OCR Refiner used fallback regex to extract problem text.")
                    return final_text
            
            print(f"Agent: Invalid output or missing <result> tags in OCR Refiner (Attempt {attempt+1}/{max_retries}). Retrying with temp {temp}...")
            print(f"RAW: {repr(llm_response)}")
            
    print("Agent: Failed to generate clean text. Applying raw text fallback.")
    return "[AI 정제 실패: 원본 텍스트를 반환합니다]\n\n" + raw_text

@app.post("/api/ai/refine", dependencies=[Depends(verify_token)])
async def refine_problem(request: RefineRequest):
    """
    Takes raw problem text and refines it into a clean Baekjoon style problem.
    """
    if not request.raw_text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")
        
    refined_text = await refine_text_with_llm(request.raw_text)
    return {"refined_text": refined_text}

@app.post("/api/ai/ocr", dependencies=[Depends(verify_token)])
async def extract_and_refine_problem(file: UploadFile = File(...)):
    """
    1. Runs OCR on uploaded image (offloaded to thread).
    2. Returns raw text immediately.
    """
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_img:
        temp_img_path = temp_img.name

    try:
        content = await file.read()
        # Offload CPU-heavy OpenCV processing
        await asyncio.to_thread(process_image_sync, content, temp_img_path)
        
        # Offload CPU-heavy PaddleOCR execution
        result = await asyncio.to_thread(ocr.ocr, temp_img_path)
        raw_text = ""
        if result and result[0]:
            for line in result[0]:
                text = line[1][0]
                raw_text += text + "\n"
        
        if not raw_text.strip():
            return {"error": "No text detected in the image."}

        return {
            "raw_text": raw_text.strip()
        }

    finally:
        if os.path.exists(temp_img_path):
            os.remove(temp_img_path)

@app.post("/api/ai/testcase", dependencies=[Depends(verify_token)])
async def generate_testcase(request: TestcaseRequest):
    """
    Analyzes problem text and generates exactly 1 edge test case in JSON format.
    """
    prompt = f"""
You are an expert test case generator for a strict algorithm Judge system.
Read the problem description below and generate exactly 1 challenging edge test case.

Problem Description:
{request.problem_text}

You MUST answer ONLY in the following JSON format. NEVER include markdown or extra explanations. The values for "input" and "expected_output" must be strings.
{{
  "input": "Write the input string here",
  "expected_output": "Write the expected output string here"
}}
"""
    max_retries = 5
    async with httpx.AsyncClient() as client:
        for attempt in range(max_retries):
            response = await call_ollama(client, prompt, format_json=True)
            try:
                parsed = robust_parse_json(response)
                return parsed
            except Exception:
                print(f"Agent: Failed to parse testcase (Attempt {attempt+1}/{max_retries}). Retrying...")
    raise HTTPException(status_code=500, detail="Failed to parse AI generated testcase after retries.")

@app.post("/api/ai/testcases", dependencies=[Depends(verify_token)])
async def generate_testcases(request: TestcaseRequest):
    """
    Analyzes problem text and generates exactly 5 edge test cases in JSON object format.
    Guarantees returning 5 test cases even if LLM generates fewer.
    """
    prompt = f"""
You are an expert test case generator for a strict algorithm Judge system.
Read the problem description below and generate exactly 5 distinct test cases, including challenging and tricky edge cases.

Problem Description:
{request.problem_text}

You MUST answer ONLY in the following JSON Object format. You must provide exactly 5 test cases inside the "testcases" array. NEVER include markdown or extra explanations.
{{
  "testcases": [
    {{
      "input": "first input string (e.g. 10 20\\n)",
      "expected_output": "first expected output string (e.g. 30)"
    }},
    {{
      "input": "second input string",
      "expected_output": "second expected output string"
    }},
    {{
      "input": "third input string",
      "expected_output": "third expected output string"
    }},
    {{
      "input": "fourth input string",
      "expected_output": "fourth expected output string"
    }},
    {{
      "input": "fifth input string",
      "expected_output": "fifth expected output string"
    }}
  ]
}}
"""
    max_retries = 5
    tc_list = []
    fallback_extras = [
        {"input": "10 20\n", "expected_output": "30"},
        {"input": "0 0\n", "expected_output": "0"},
        {"input": "-5 5\n", "expected_output": "0"},
        {"input": "100 200\n", "expected_output": "300"},
        {"input": "999 1\n", "expected_output": "1000"}
    ]
    
    async with httpx.AsyncClient() as client:
        for attempt in range(max_retries):
            response = await call_ollama(client, prompt, format_json=True)
            print(f"Ollama raw response for testcases (Attempt {attempt+1}/{max_retries}): {response}")
            try:
                parsed = robust_parse_json(response)
                if isinstance(parsed, list):
                    tc_list = parsed
                    break
                elif isinstance(parsed, dict) and "testcases" in parsed and isinstance(parsed["testcases"], list):
                    tc_list = parsed["testcases"]
                    break
                elif isinstance(parsed, dict) and "input" in parsed:
                    tc_list = [parsed]
                    break
            except Exception as e:
                print(f"Failed robust JSON parse (Attempt {attempt+1}/{max_retries}): {e}")

    # Guarantee exactly 5 testcases
    while len(tc_list) < 5:
        tc_list.append(fallback_extras[len(tc_list) % len(fallback_extras)])
        
    return {"testcases": tc_list[:5]}

@app.post("/api/ai/hint", dependencies=[Depends(verify_token)])
async def get_hint(request: HintRequest):
    """
    Analyzes failed code and provides a hint based on time/space complexity.
    """
    prompt = f"""
You are the best algorithm coding test tutor.
The student's code below has either failed or timed out while solving the following problem.
We also provide you with the Teacher's Correct Answer Code for your reference.
Please carefully compare the Student's Failed Code with the Teacher's Correct Answer Code.
Identify the logical flaws, missing edge cases, or inefficiencies in the student's code.

DO NOT provide the direct answer or full correct code to the student. 
Provide ONLY the core logical 'hints' and explanations of what went wrong in markdown format.

**[WARNING: You MUST respond ONLY in Korean (한국어). NEVER use Chinese or English for the explanation.]**

--- Problem ---
{request.problem_text}

--- Teacher's Correct Answer Code ---
{request.answer_code or "Not provided"}

--- Student's Failed Code ---
{request.failed_code}
"""
    async with httpx.AsyncClient() as client:
        hint = await call_ollama(client, prompt)
    return {"hint": hint}

EDGE_CASE_SYSTEM_PROMPT = (
    "당신은 알고리즘 채점 서버의 엣지 케이스 및 반례 설계 전문가입니다.\n"
    "주어진 문제 설명과 정답 코드를 분석하여 치명적인 엣지 케이스(반례)를 생성하세요.\n"
    "[생성 규칙 - 엄수!]\n"
    "1. [가장 중요] 'generator_code' 항목에는 오직 파이썬으로 `eval()` 가능한 문자열 생성 코드(Python Expression) 또는 원시 문자열(Raw string)만 적으세요. 절대 설명글을 적지 마세요!\n"
    "2. 반드시 100% 순수 한국어로만 작성하세요.\n"
    "3. [제약 조건 엄수] 반례는 반드시 주어진 문제의 제약 조건(범위, 중복 허용 여부 등)과 입력 형식을 100% 지켜야 합니다. 조건을 위반하지 않는 선에서 최대값, 최소값, 극단적 상황, 특수 패턴 등 오답이나 시간 초과(TLE)를 유발할 수 있는 데이터를 포함하세요.\n"
    "4. 'reason'(이유 설명)과 'case_name'은 무조건 100% 순수 한국어로 명확히 적으세요.\n"
    "5. 반드시 다음과 같은 JSON 배열 구조로 응답해야 합니다:\n"
    "[\n"
    "  {\n"
    "    \"case_name\": \"유형 이름\",\n"
    "    \"generator_code\": \"파이썬 수식\",\n"
    "    \"reason\": \"이유 설명\"\n"
    "  }\n"
    "]"
)

async def call_coder_ai_async(client: httpx.AsyncClient, problem_text: str, error_feedback: str = None, previous_code: str = None, failed_input: str = None) -> str:
    chat_url = OLLAMA_URL.replace("/api/generate", "/api/chat")
    
    if not error_feedback:
        system_prompt = (
            "당신은 알고리즘 전문가입니다. 주어진 문제의 제약 조건을 완벽하게 준수하여 최적의 알고리즘 답 코드를 생성하세요."
            " 어떤 부가 설명도 없이 오직 ```python ... ``` 블록으로만 응답하세요. "
            "절대 `input()` 함수를 사용하지 마세요! 모든 입력은 반드시 `import sys; data = sys.stdin.read().split()` 방식으로만 처리해야 합니다."
        )
        user_prompt = problem_text
    else:
        system_prompt = (
            "당신은 알고리즘 전문가입니다. 이전 코드에서 발생한 오류를 수정하여 완전하고 올바른 Python 코드를 작성하세요."
            " 어떤 부가 설명도 없이 오직 ```python ... ``` 블록으로만 응답하세요. "
            "절대 `input()` 함수를 사용하지 마세요! 모든 입력은 반드시 `import sys; data = sys.stdin.read().split()` 방식으로만 처리해야 합니다."
        )
        user_prompt = f"[문제 설명]\n{problem_text}\n\n[이전 코드]\n{previous_code}\n\n[실패한 입력]\n{failed_input}\n\n[오류 또는 틀린 출력 피드백]\n{error_feedback}\n\n모든 버그를 수정하고 완전히 동작하는 Python 솔루션을 작성하세요."

    payload = {
        "model": "code-generator-ai",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "stream": False,
        "options": {
            "num_ctx": 16384
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

async def call_ollama_edge_case(client: httpx.AsyncClient, problem_text: str) -> list:
    chat_url = OLLAMA_URL.replace("/api/generate", "/api/chat")
    user_prompt = problem_text
    
    max_retries = 10
    for attempt in range(max_retries):
        temp = 0.2 + (attempt * 0.1)
        payload = {
            "model": "edge-case-ai",
            "messages": [
                {"role": "system", "content": EDGE_CASE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False,
            "options": {"temperature": temp, "num_ctx": 8192}
        }
        
        try:
            response = await client.post(chat_url, json=payload, timeout=60.0)
            response.raise_for_status()
            content = response.json().get("message", {}).get("content", "")
            
            if re.search(r'[一-鿿]', content):
                print(f"Edge Case Gen: Attempt {attempt+1} contained Chinese. Retrying with temp {temp}...")
                continue
                
            try:
                cases = robust_parse_json(content)
            except Exception:
                print(f"Edge Case Gen Error: Could not parse JSON. Retrying with temp {temp}...")
                continue
            
            # Normalize: support both old 'generator_code' and new 'input' field
            normalized = []
            if isinstance(cases, dict):
                cases = [cases]
                
            if isinstance(cases, list):
                for case in cases:
                    if isinstance(case, dict):
                        if "input" in case:
                            normalized.append(case)
                        elif "generator_code" in case:
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
"You are a fair Algorithm Judge AI. You are reviewing the Execution Results of 3 Coder AIs who ran their Python code against the [Input] generated by a Tester AI.\n"
    "Your job is to determine who is at fault and identify the correct expected output.\n"
    "[CORE ASSUMPTION]\n"
    "All Coder AIs MUST parse input using: `import sys; data = sys.stdin.read().split()`\n"
    "This method treats both newlines (\\n) and spaces ( ) as delimiters.\n"
    "Therefore, formatting differences like 'all values on one line' or 'no newlines' are NEVER the Tester's fault!\n"
    "[JUDGMENT CRITERIA]\n"
    "1. Tester AI fault (TESTER): Applies if the input violates constraints (count, bounds, types) OR if the input is LOGICALLY IMPOSSIBLE (e.g., mathematically contradictory constraints, or violating the fundamental timeline/physical rules of the problem). Formatting is NOT a fault.\n"
    "2. Coder AI fault (CODER): Applies if the input is perfectly valid AND logically possible, but ALL 3 Coder AIs either produced incorrect outputs or threw errors.\n"
    "3. Normal (NONE): The input is valid, and AT LEAST 1 Coder AI produced the correct expected output.\n"
    "[STRICT FORMAT]\n"
    "You MUST respond ONLY in the JSON format below. DO NOT include markdown.\n"
    "{\n"
    "  \"fault\": \"CODER\" | \"TESTER\" | \"NONE\",\n"
    "  \"logical_analysis\": \"입력값이 문제의 논리에 어긋나지 않는지, 에러의 진짜 원인이 누구에게 있는지 분석 (한국어)\",\n"
    "  \"expected_output\": \"The correct output string (only required if fault is NONE, otherwise empty string)\",\n"
    "  \"reason\": \"최종 판결 이유 (한국어)\"\n"
    "}"
)

async def call_judge_ai(client: httpx.AsyncClient, problem_text: str, test_input: str, outputs: list) -> dict:
    chat_url = OLLAMA_URL.replace("/api/generate", "/api/chat")
    user_prompt = f"[Problem Description]\n{problem_text}\n\n[Input value provided by Tester]\n{test_input}\n\n[Execution Results from Coders]\n"
    for i, out in enumerate(outputs):
        user_prompt += f"Coder {i+1}: {out}\n"
    user_prompt += "\nAnalyze the above results, determine who is at fault, and provide the correct expected output."
    
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
        response = await client.post(chat_url, json=payload, timeout=60.0)
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

async def call_verifier_ai(client: httpx.AsyncClient, problem_text: str, test_input: str, test_output: str) -> dict:
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
        response = await client.post(chat_url, json=payload, timeout=60.0)
        response.raise_for_status()
        content = response.json().get("message", {}).get("content", "")
        parsed = json.loads(content)
        return parsed
    except Exception as e:
        print(f"Verifier AI Error: {e}")
        return {"is_correct": True, "reason": "Verifier AI failed, assuming true."}

def parse_sample_cases(problem_text: str) -> list:
    cases = []
    blocks = re.split(r'(?=예제\s*입력\s*\d+|Sample\s*Input\s*\d+)', problem_text, flags=re.IGNORECASE)
    for block in blocks:
        inp_m = re.search(r'(?:예제\s*입력|Sample\s*Input)\s*\d*\s*\n([\s\S]*?)(?:예제\s*출력|Sample\s*Output|Expected)', block, re.IGNORECASE)
        out_m = re.search(r'(?:예제\s*출력|Sample\s*Output|Expected)\s*\d*\s*\n([\s\S]*?)(?:예제\s*입력|Sample\s*Input|$)', block, re.IGNORECASE)
        if inp_m and out_m:
            inp = inp_m.group(1).strip()
            out = out_m.group(1).strip()
            if inp and out:
                cases.append({"input": inp, "output": out})
    
    if cases: return cases
    
    inp_m = re.search(r'(?:예제\s*입력|Sample\s*Input)[^\n]*\n([\s\S]*?)(?:예제\s*출력|Sample\s*Output)', problem_text, re.IGNORECASE)
    out_m = re.search(r'(?:예제\s*출력|Sample\s*Output)[^\n]*\n([\s\S]*?)(?:\n\n|$)', problem_text, re.IGNORECASE)
    if inp_m and out_m:
        inp = inp_m.group(1).strip()
        out = out_m.group(1).strip()
        if inp and out:
            cases.append({"input": inp, "output": out})
    return cases

async def run_code_against_input(code: str, test_input: str) -> str:
    """Run python code securely using a transient Docker container (DooD)."""
    import base64
    
    # Encode code and input to base64 to avoid any quoting/escaping issues
    code_b64 = base64.b64encode(code.encode('utf-8')).decode('utf-8')
    input_b64 = base64.b64encode(test_input.encode('utf-8')).decode('utf-8')
    
    wrapper_script = f"""
import sys, io, base64
sys.stdin = io.StringIO(base64.b64decode('{input_b64}').decode('utf-8'))
exec(base64.b64decode('{code_b64}').decode('utf-8'), {{"__name__": "__main__", "sys": sys}})
"""

    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "run", "--rm", "-i",
            "--network", "none",
            "--memory", "128m",
            "--cpus", "0.5",
            "python:3.10-slim",
            "python", "-",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(input=wrapper_script.encode('utf-8')), timeout=5.0)
            if proc.returncode == 0:
                return stdout.decode('utf-8').strip()
            else:
                return f"ERROR: {stderr.decode('utf-8').strip()[:200]}"
        except asyncio.TimeoutError:
            proc.kill()
            return "ERROR: TimeoutError"
            
    except Exception as e:
        return f"ERROR: Sandbox execution failed: {e}"

async def pre_validate_samples(client: httpx.AsyncClient, request: EdgeCaseRequest, solution_codes: list) -> tuple:
    final_solution_code = solution_codes[0]
    sample_cases = parse_sample_cases(request.problem_text)
    
    if not sample_cases:
        print("Agent: No sample cases found in problem text. Skipping pre-validation.")
        return final_solution_code, True
        
    print(f"Agent: Found {len(sample_cases)} sample case(s). Running pre-validation...")
    sample_passed = False
    
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
            
    return final_solution_code, sample_passed

async def run_coder_tester_loop(client: httpx.AsyncClient, request: EdgeCaseRequest, ai_cases: list, solution_codes: list) -> dict:
    max_agent_retries = 10
    final_testcases = []
    judge_logs = []
    case_fail_counts = {}
    blacklist_cases = set()
    
    for attempt in range(max_agent_retries):
        print(f"Agent Loop: Testing Coder's codes (Attempt {attempt+1}/{max_agent_retries})")
        code_failed = False
        failed_error = ""
        failed_input = ""
        successful_cases = []
        surviving_code_indices = list(range(len(solution_codes)))
        
        for idx, case in enumerate(ai_cases):
            case_name = case.get("case_name", f"Edge Case {idx+1}")
            if case_name in blacklist_cases:
                continue
            
            actual_input = case.get("input", "")
            if not actual_input: continue
            
            actual_input = actual_input.strip()
            if not actual_input: continue
            
            # (Removed hardcoded router validation here to support general problems)
            
            run_tasks = [run_code_against_input(solution_codes[i], actual_input) for i in surviving_code_indices]
            outputs = await asyncio.gather(*run_tasks)
            
            error_types = []
            for o in outputs:
                if "IndexError" in o or "list index out of range" in o: error_types.append("IndexError")
                elif "ValueError" in o: error_types.append("ValueError")
                elif "NameError" in o: error_types.append("NameError")
                
            if len(error_types) == len(outputs) and len(set(error_types)) == 1:
                err_type = error_types[0]
                case_fail_counts[case_name] = case_fail_counts.get(case_name, 0) + 1
                if case_fail_counts[case_name] >= 3:
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
                judge_result = await call_judge_ai(client, request.problem_text, actual_input, outputs)
                
                judge_logs.append({
                    "attempt": attempt + 1,
                    "case_name": case_name,
                    "fault": judge_result.get("fault", "CODER"),
                    "reason": judge_result.get("reason", "")
                })
                
                if judge_result.get("fault") == "TESTER":
                    continue
                elif judge_result.get("fault") == "CODER":
                    error_count = sum(1 for o in outputs if o.startswith("ERROR:"))
                    if error_count == len(outputs):
                        code_failed = True
                        failed_error = f"Judge AI 판결 (CODER 잘못): {judge_result.get('reason')}\n출력결과들: {outputs}"
                        failed_input = actual_input
                        break
                    else:
                        from collections import Counter
                        cnt = Counter(o for o in outputs if not o.startswith("ERROR:"))
                        expected_output = cnt.most_common(1)[0][0]
                else:
                    expected_output = str(judge_result.get("expected_output", unique_outputs[0] if unique_outputs else ""))
            else:
                expected_output = unique_outputs[0]
                
            new_surviving = []
            for i, o in zip(surviving_code_indices, outputs):
                if o == expected_output:
                    new_surviving.append(i)
            surviving_code_indices = new_surviving
            
            if not surviving_code_indices:
                code_failed = True
                failed_error = f"Logical Error: AI outputs diverged and all surviving codes failed to produce the correct expected output: {expected_output}."
                failed_input = actual_input
                break
                
            successful_cases.append({
                "case_name": case_name,
                "reason": case.get("reason", ""),
                "input": actual_input,
                "expected_output": expected_output
            })
                    
        if not code_failed and len(successful_cases) >= 3 :
            final_testcases = successful_cases
            return {
                "solution_code": solution_codes[surviving_code_indices[0]],
                "testcases": final_testcases,
                "judge_logs": judge_logs
            }
        else:
            print(f"Agent: Coder AI codes failed. Requesting self-healing... Error: {failed_error[:100]}")
            if attempt < max_agent_retries - 1:
                tasks = [call_coder_ai_async(client, request.problem_text, failed_error, solution_codes[surviving_code_indices[0] if surviving_code_indices else 0], failed_input) for _ in range(3)]
                solution_codes = await asyncio.gather(*tasks)
                solution_codes = [c for c in solution_codes if c]
                if not solution_codes:
                    break
                surviving_code_indices = list(range(len(solution_codes)))
                
    print(f"Agent: Max retries ({max_agent_retries}) reached. Returning best available code.")
    if solution_codes:
        return {
            "solution_code": solution_codes[0],
            "testcases": successful_cases[:5],
            "judge_logs": judge_logs
        }
    else:
        return {
            "error": "Multi-Agent loop failed to generate valid code and testcases.",
            "judge_logs": judge_logs
        }

@app.post("/api/ai/edge-cases", dependencies=[Depends(verify_token)])
async def generate_full_edge_cases(request: EdgeCaseRequest):
    async with httpx.AsyncClient() as client:
        print("Agent: Requesting edge cases from Tester AI...")
        ai_cases = await call_ollama_edge_case(client, request.problem_text)
        if not ai_cases:
            return {"error": "Failed to generate valid JSON testcases."}

        print("Agent: Requesting 3 different solutions from Coder AI concurrently...")
        tasks = [call_coder_ai_async(client, request.problem_text) for _ in range(3)]
        solution_codes = await asyncio.gather(*tasks)
        
        solution_codes = [c for c in solution_codes if c]
        if not solution_codes:
            return {"error": "Failed to generate python code."}
            
        final_solution_code, sample_passed = await pre_validate_samples(client, request, solution_codes)
        
        if not sample_passed:
            print("Agent: WARNING - Could not generate code that passes sample cases.")
            return {"error": "Failed to generate code that passes the sample test cases after multiple attempts."}
            
        solution_codes[0] = final_solution_code
        
        result = await run_coder_tester_loop(client, request, ai_cases, solution_codes)
        return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
