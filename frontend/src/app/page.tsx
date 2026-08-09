"use client";

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Editor from '@monaco-editor/react';
import { Play, Terminal, BookOpen, CheckCircle, XCircle, Clock, LayoutDashboard, LogOut, Plus, Trash2, Sparkles, Layers, Bookmark, Save, FolderOpen, Image as ImageIcon, UploadCloud, Loader2, Search } from 'lucide-react';
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from "react-resizable-panels";
import { fetchEventSource } from '@microsoft/fetch-event-source';

interface TestCase {
  input: string;
  expected_output: string;
  status?: 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAIL' | 'ERROR' | 'TIMEOUT';
  output?: string;
  exec_time?: number;
  memory_kb?: number;
}

export default function JudgePage() {
  const router = useRouter();
  const [activeCodeTab, setActiveCodeTab] = useState<'answer' | 'mycode'>('mycode');
  const [answerCode, setAnswerCode] = useState<string>('import sys\ndata = sys.stdin.read().split()\n');
  const [myCode, setMyCode] = useState<string>('import sys\ndata = sys.stdin.read().split()\n# Your code here');
  const [problemText, setProblemText] = useState<string>('');
  const [language, setLanguage] = useState<string>('python');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [output, setOutput] = useState<string>('');
  const [status, setStatus] = useState<string>('READY');
  const [user, setUser] = useState<{ email: string; username: string } | null>(null);

  const [isMobile, setIsMobile] = useState<boolean>(false);
  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 1024);
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Testcase & Tab management
  const [activeTab, setActiveTab] = useState<'upload' | 'problem' | 'testcases'>('upload');
  const [isGeneratingTc, setIsGeneratingTc] = useState<boolean>(false);
  const [isOcrLoading, setIsOcrLoading] = useState<boolean>(false);
  const [isRefining, setIsRefining] = useState<boolean>(false);
  const [rawOcrText, setRawOcrText] = useState<string>('');
  const [uploadedImagePreview, setUploadedImagePreview] = useState<string | null>(null);
  const [testCases, setTestCases] = useState<TestCase[]>([
    { input: "10 10\n", expected_output: "20" }
  ]);
  const [problemTitle, setProblemTitle] = useState<string>('');
  const [savedProblems, setSavedProblems] = useState<any[]>([]);
  const [isProblemModalOpen, setIsProblemModalOpen] = useState<boolean>(false);
  const [isSavingProblem, setIsSavingProblem] = useState<boolean>(false);
  const [isLoadingProblems, setIsLoadingProblems] = useState<boolean>(false);

  const fetchSavedProblems = async () => {
    setIsLoadingProblems(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch('/api/problems', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.status === 401) {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        router.push('/login');
        return;
      }
      if (res.ok) {
        const data = await res.json();
        setSavedProblems(Array.isArray(data) ? data : []);
      }
    } catch (err) {
      console.error("Failed to fetch problems", err);
    } finally {
      setIsLoadingProblems(false);
    }
  };

  const handleOpenProblemModal = () => {
    fetchSavedProblems();
    setIsProblemModalOpen(true);
  };

  const handleSaveProblem = async () => {
    if (!problemText.trim()) {
      alert("문제 설명을 먼저 작성해주세요!");
      setActiveTab('problem');
      return;
    }
    setIsSavingProblem(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch('/api/problems', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          title: problemTitle.trim() || "제목 없는 문제",
          description: problemText,
          code: answerCode,
          timeLimitMs: 2000,
          memoryLimitMb: 256,
          testCases: testCases.map(tc => ({
            input: tc.input,
            expected_output: tc.expected_output
          }))
        })
      });
      if (res.ok) {
        alert("🎉 문제, 코드, 테스트케이스 셋이 성공적으로 저장되었습니다!");
        fetchSavedProblems();
      } else {
        const data = await res.json();
        alert("저장 실패: " + (data.error || "알 수 없는 오류"));
      }
    } catch (err: any) {
      alert("저장 중 오류 발생: " + err.message);
    } finally {
      setIsSavingProblem(false);
    }
  };

  const handleLoadProblem = async (id: number) => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`/api/problems/${id}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setProblemTitle(data.title || '');
        setProblemText(data.description || '');
        if (data.code !== undefined && data.code !== null) {
          setAnswerCode(data.code);
        }
        if (data.testCases && Array.isArray(data.testCases) && data.testCases.length > 0) {
          setTestCases(data.testCases.map((tc: any) => ({
            input: tc.input || "",
            expected_output: tc.expected_output || tc.expectedOutput || "",
            status: 'PENDING'
          })));
        }
        setIsProblemModalOpen(false);
        setActiveTab('problem');
        alert(`📚 '${data.title}' 문제, 코드, 테스트케이스를 불러왔습니다!`);
      }
    } catch (err: any) {
      alert("불러오기 실패: " + err.message);
    }
  };

  const handleDeleteProblem = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("정말 이 문제와 속한 테스트케이스들을 삭제하시겠습니까?")) return;
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`/api/problems/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        fetchSavedProblems();
      }
    } catch (err) {
      console.error("Delete problem error", err);
    }
  };

  useEffect(() => {
    const token = localStorage.getItem('token');
    const userData = localStorage.getItem('user');

    if (!token || !userData) {
      router.push('/login');
    } else {
      setUser(JSON.parse(userData));
      fetch(`/api/users/me/submissions/latest`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
        .then(async res => {
          if (!res.ok) return {};
          const text = await res.text();
          return text ? JSON.parse(text) : {};
        })
        .then(data => {
          if (data && data.problemText !== undefined) {
            setProblemText(data.problemText);
            if (data.code) setMyCode(data.code);
            if (data.testCases && Array.isArray(data.testCases) && data.testCases.length > 0) {
              setTestCases(data.testCases.map((tc: any) => ({
                input: tc.input || "",
                expected_output: tc.expected_output || tc.expectedOutput || "",
                status: 'PENDING'
              })));
            }
          }
        })
        .catch(err => console.error("Failed to fetch latest submission", err));
    }
  }, [router]);

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    router.push('/login');
  };

  const handleEditorChange = (value: string | undefined) => {
    if (value !== undefined) {
      if (activeCodeTab === 'answer') setAnswerCode(value);
      else setMyCode(value);
    }
  };

  const handleGenerateTestcases = async () => {
    if (!problemText.trim()) {
      alert("문제를 먼저 입력해주세요!");
      setActiveTab('problem');
      return;
    }
    const token = localStorage.getItem('token');
    setIsGeneratingTc(true);
    setActiveTab('testcases');
    let attempt = 0;
    const maxRetries = 10;
    let success = false;

    while (attempt < maxRetries && !success) {
      attempt++;
      setOutput(prev => prev + `\n[🤖 AI] 문제 분석 및 엣지 테스트케이스 5개 생성 중... (시도 ${attempt}/${maxRetries})\n`);

      try {
        // Use direct backend URL to bypass Next.js 30-second proxy timeout limit
        const aiApiUrl = process.env.NEXT_PUBLIC_AI_API_URL || 'http://localhost:8000';
        const response = await fetch(`${aiApiUrl}/api/ai/edge-cases`, {
          method: 'POST',

          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
            'ngrok-skip-browser-warning': 'true'
          },
          body: JSON.stringify({
            problem_text: problemText,
          }),
        });

        const data = await response.json();

        if (response.status === 401) {
          localStorage.removeItem('token');
          localStorage.removeItem('user');
          router.push('/login');
          return;
        }

        let logsMsg = "";
        if (data && data.judge_logs && data.judge_logs.length > 0) {
          logsMsg += `\n=== 🔎 [AI 멀티-에이전트 심판 로그] ===\n`;
          data.judge_logs.forEach((log: any) => {
            logsMsg += `[Attempt ${log.attempt} - ${log.case_name}]\n`;
            logsMsg += `👉 판결: ${log.fault === 'NONE' ? '✅ 패스' : `❌ ${log.fault} 잘못`}\n`;
            logsMsg += `👉 사유: ${log.reason}\n\n`;
          });
          logsMsg += `====================================\n\n`;
        }

        if (!response.ok || data.error) {
          setOutput(prev => prev + logsMsg + `[🤖 AI Error] ${data.error || "테스트케이스 생성 실패"}\n`);
          if (attempt === maxRetries) {
            alert("AI 엣지 케이스 생성 실패 (최대 재시도 초과): " + (data.error || "서버 오류"));
          } else {
            setOutput(prev => prev + `[🤖 AI] 실패 감지됨. 즉시 재시도합니다...\n`);
          }
          continue;
        }

        if (data && data.testcases && Array.isArray(data.testcases)) {
          setTestCases(data.testcases.map((tc: any) => ({
            input: tc.input || "",
            expected_output: tc.expected_output || tc.expectedOutput || "",
            status: 'PENDING'
          })));
          let successMsg = logsMsg + `[🤖 AI] 엣지 테스트케이스 ${data.testcases.length}개 생성 완료!\n`;
          if (data.solution_code) {
            setAnswerCode(data.solution_code);
            successMsg += `[🤖 AI] 자가 치유(Self-Healing) 및 최종 검증을 통과한 최적화 정답 코드가 에디터에 적용되었습니다!\n`;
          }
          setOutput(prev => prev + successMsg);
          success = true; // Mark as success to exit the loop
        }
      } catch (error: any) {
        setOutput(prev => prev + `[🤖 AI Error] ${error.message}\n`);
        if (attempt === maxRetries) {
          alert("AI 엣지 케이스 생성에 실패했습니다: " + error.message);
        } else {
          setOutput(prev => prev + `[🤖 AI] 네트워크 또는 런타임 오류 감지됨. 즉시 재시도합니다...\n`);
        }
      }
    }

    setIsGeneratingTc(false);
  };

  const handleRefineProblem = async () => {
    if (!problemText.trim()) {
      alert("문제를 먼저 입력해주세요!");
      return;
    }
    const token = localStorage.getItem('token');
    setIsRefining(true);
    setOutput(prev => prev + `\n[🤖 AI] 작성된 텍스트를 백준 스타일로 정제 중...\n`);

    try {
      const aiApiUrl = process.env.NEXT_PUBLIC_AI_API_URL || 'http://localhost:8000';
      const response = await fetch(`${aiApiUrl}/api/ai/refine`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
          'ngrok-skip-browser-warning': 'true'
        },
        body: JSON.stringify({ raw_text: problemText }),
      });

      const data = await response.json();

      if (response.status === 401) {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        router.push('/login');
        return;
      }

      if (!response.ok || data.error) {
        throw new Error(data.error || "정제 실패");
      }

      setProblemText(data.refined_text);
      setOutput(prev => prev + `[🤖 AI] 백준 스타일로 문제 정제 완료! 편집 창에 적용되었습니다.\n`);
    } catch (error: any) {
      setOutput(prev => prev + `[🤖 AI Error] ${error.message}\n`);
      alert("AI 정제 실패: " + error.message);
    } finally {
      setIsRefining(false);
    }
  };

  const handleRefineFromOcr = async () => {
    if (!rawOcrText.trim()) {
      alert("추출된 텍스트가 없습니다.");
      return;
    }
    const token = localStorage.getItem('token');
    setIsRefining(true);
    setOutput(prev => prev + `\n[🤖 AI] 원본 OCR 텍스트를 백준 스타일로 정제 중...\n`);

    try {
      const aiApiUrl = process.env.NEXT_PUBLIC_AI_API_URL || 'http://localhost:8000';
      const response = await fetch(`${aiApiUrl}/api/ai/refine`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
          'ngrok-skip-browser-warning': 'true'
        },
        body: JSON.stringify({ raw_text: rawOcrText }),
      });

      const data = await response.json();

      if (response.status === 401) {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        router.push('/login');
        return;
      }

      if (!response.ok || data.error) {
        throw new Error(data.error || "정제 실패");
      }

      setProblemText(data.refined_text);
      setRawOcrText('');
      setUploadedImagePreview(null);
      setOutput(prev => prev + `[🤖 AI] 정제 완료! 문제 편집 창에 적용되었습니다.\n`);
      setActiveTab('problem');
    } catch (error: any) {
      setOutput(prev => prev + `[🤖 AI Error] ${error.message}\n`);
      alert("AI 정제 실패: " + error.message);
    } finally {
      setIsRefining(false);
    }
  };

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];

    // Create a local preview URL for the image
    setUploadedImagePreview(URL.createObjectURL(file));

    setIsOcrLoading(true);
    setOutput(prev => prev + `\n[🤖 AI] 이미지에서 문제 텍스트 추출 중...\n`);

    const formData = new FormData();
    formData.append("file", file);

    const token = localStorage.getItem('token');
    try {
      // Use direct backend URL to bypass Next.js 30-second proxy timeout limit
      const aiApiUrl = process.env.NEXT_PUBLIC_AI_API_URL || 'http://localhost:8000';
      const res = await fetch(`${aiApiUrl}/api/ai/ocr`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'ngrok-skip-browser-warning': 'true'
        },
        body: formData
      });

      if (res.status === 401) {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        router.push('/login');
        return;
      }

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "OCR 실패");

      let ocrLog = `[🤖 AI] 문제 텍스트 추출 완료!\n\n`;
      if (data.raw_text) {
        ocrLog += `=== 🔍 [원본 OCR 텍스트] ===\n${data.raw_text}\n============================\n\n`;
      }
      ocrLog += `[🤖 AI] 업로드 탭에서 텍스트를 확인하고 정제 버튼을 눌러주세요.\n`;

      setRawOcrText(data.raw_text || '');
      setOutput(prev => prev + ocrLog);
      // Removed: setActiveTab('problem');
    } catch (err: any) {
      alert("이미지 처리 실패: " + err.message);
      setOutput(prev => prev + `[🤖 AI Error] ${err.message}\n`);
    } finally {
      setIsOcrLoading(false);
      // reset file input
      e.target.value = '';
    }
  };

  const handleAddTestcase = () => {
    setTestCases(prev => [...prev, { input: "", expected_output: "", status: 'PENDING' }]);
  };

  const handleDeleteTestcase = (index: number) => {
    if (testCases.length <= 1) {
      alert("최소 1개의 테스트케이스는 필요합니다.");
      return;
    }
    setTestCases(prev => prev.filter((_, idx) => idx !== index));
  };

  const handleTestcaseChange = (index: number, field: 'input' | 'expected_output', value: string) => {
    setTestCases(prev => prev.map((tc, idx) => {
      if (idx === index) {
        return { ...tc, [field]: value, status: 'PENDING' };
      }
      return tc;
    }));
  };

  const handleSubmit = async () => {
    if (isSubmitting) return;

    const token = localStorage.getItem('token');
    if (!token) {
      router.push('/login');
      return;
    }

    if (!problemText.trim()) {
      setOutput('오류: 문제를 먼저 입력해주세요!');
      setActiveTab('problem');
      return;
    }
    const activeCode = activeCodeTab === 'answer' ? answerCode : myCode;
    if (!activeCode.trim()) {
      setOutput('오류: 코드를 먼저 작성해주세요!');
      return;
    }

    setIsSubmitting(true);
    setStatus('PENDING');
    setActiveTab('testcases');
    setTestCases(prev => prev.map(tc => ({ ...tc, status: 'RUNNING', output: undefined, exec_time: undefined })));
    setOutput('Submitting to Judge Server (Parallel Multi-TC Evaluation)...\n');

    try {
      const response = await fetch(`/api/submissions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          problemText: problemText,
          code: activeCodeTab === 'answer' ? answerCode : myCode,
          language: language,
          testCases: testCases.map(tc => ({
            input: tc.input,
            expected_output: tc.expected_output
          }))
        }),
      });

      if (response.status === 401) {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        router.push('/login');
        return;
      }

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to submit code');
      }

      const submissionId = data.submission_id;
      setOutput(prev => prev + `Submission successful! (ID: ${submissionId})\nParallel workers executing ${testCases.length} test cases...\n`);

      const ctrl = new AbortController();

      await fetchEventSource(`/api/submissions/${submissionId}/stream`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Accept': 'text/event-stream'
        },
        signal: ctrl.signal,
        async onopen(response) {
          if (response.ok && response.headers.get('content-type')?.includes('text/event-stream')) {
            return; // everything's good
          } else if (response.status === 401) {
            localStorage.removeItem('token');
            localStorage.removeItem('user');
            router.push('/login');
            ctrl.abort();
          } else {
            throw new Error(`Failed to connect (status ${response.status})`);
          }
        },
        onmessage(msg) {
          if (msg.event === 'connect') {
            setOutput(prev => prev + `[Connected] ${msg.data}\nWaiting for worker pool...\n`);
          } else if (msg.event === 'testcase_result') {
            const result = JSON.parse(msg.data);
            setTestCases(prev => prev.map((tc, idx) => {
              if (idx === result.index - 1) {
                return {
                  ...tc,
                  status: result.status === 'SUCCESS' ? 'SUCCESS' : 'FAIL',
                  output: result.output,
                  exec_time: result.exec_time,
                  memory_kb: result.memory_kb
                };
              }
              return tc;
            }));
          } else if (msg.event === 'judge_result') {
            const result = JSON.parse(msg.data);
            setStatus(result.status);
            
            let formattedOutput = `\n[Final Result: ${result.status}]\n`;
            if (result.output) {
              formattedOutput += `${result.output}\n`;
            }

            setOutput(prev => prev + formattedOutput);
            setIsSubmitting(false);
            ctrl.abort(); // close connection cleanly
          }
        },
        onerror(err) {
          setOutput(prev => prev + '\n[Error] Connection to stream lost.\n');
          setIsSubmitting(false);
          setStatus(prev => prev === 'PENDING' ? 'ERROR' : prev);
          ctrl.abort(); // Stop retrying
        }
      });

    } catch (error: any) {
      if (error.name === 'AbortError') return;
      setOutput(prev => prev + `\n[Error] ${error.message}\n`);
      setStatus('ERROR');
      setIsSubmitting(false);
    }
  };

  const getAiHint = async () => {
    const token = localStorage.getItem('token');
    setOutput(prev => prev + '\n[🤖 AI] 분석 중... (시간이 조금 걸릴 수 있습니다)\n');
    try {
      // Use direct backend URL to bypass Next.js 30-second proxy timeout limit
      const aiApiUrl = process.env.NEXT_PUBLIC_AI_API_URL || 'http://localhost:8000';
      const response = await fetch(`${aiApiUrl}/api/ai/hint`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
          'ngrok-skip-browser-warning': 'true'
        },
        body: JSON.stringify({
          problemText: problemText,
          failedCode: activeCodeTab === 'answer' ? answerCode : myCode,
          answer_code: answerCode,
        }),
      });

      if (response.status === 401) {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        router.push('/login');
        return;
      }

      const data = await response.json();
      if (!response.ok) throw new Error(data.error);

      setOutput(prev => prev + `\n[🤖 AI Hint]\n${data.hint}\n\n`);
    } catch (error: any) {
      setOutput(prev => prev + `\n[🤖 AI Error] ${error.message}\n`);
    }
  };

  const getStatusIcon = () => {
    switch (status) {
      case 'SUCCESS': return <CheckCircle className="text-green-400 w-5 h-5" />;
      case 'FAIL': return <XCircle className="text-red-400 w-5 h-5" />;
      case 'TIMEOUT': return <Clock className="text-yellow-400 w-5 h-5" />;
      case 'READY': return <div className="w-3 h-3 rounded-full bg-gray-400" />;
      default: return <div className="w-4 h-4 rounded-full border-2 border-t-blue-500 border-blue-200 animate-spin" />;
    }
  };

  if (!user) return null;

  return (
    <div className="min-h-screen bg-[#0f172a] text-slate-200 p-4 md:p-6 flex flex-col h-screen">
      {/* Header */}
      <header className="flex justify-between items-center mb-6 glass px-6 py-4 rounded-2xl">
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <span className="gradient-text">Agent</span>Judge
        </h1>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/50 border border-slate-700">
            <span className="text-sm text-slate-400">Status:</span>
            <span className="text-sm font-medium flex items-center gap-2">
              {status} {getStatusIcon()}
            </span>
          </div>

          <button
            onClick={handleOpenProblemModal}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-purple-900/40 hover:bg-purple-800/50 text-purple-300 hover:text-purple-200 transition-colors border border-purple-700/40 font-medium"
            title="저장된 문제와 테스트케이스 목록을 엽니다."
          >
            <FolderOpen className="w-4 h-4 text-purple-400" />
            문제 보관함
          </button>

          <button
            onClick={() => router.push('/dashboard')}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-700 hover:bg-slate-600 transition-colors"
          >
            <LayoutDashboard className="w-4 h-4" />
            Dashboard
          </button>

          <button
            onClick={handleLogout}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-red-900/50 hover:bg-red-800/50 text-red-400 hover:text-red-300 transition-colors border border-red-900/50"
            title="로그아웃"
          >
            <LogOut className="w-4 h-4" />
          </button>

          <button
            onClick={handleSubmit}
            disabled={isSubmitting}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-medium transition-all duration-300 ${isSubmitting
              ? 'bg-slate-700 text-slate-400 cursor-not-allowed'
              : 'bg-blue-600 hover:bg-blue-500 hover:shadow-[0_0_20px_rgba(59,130,246,0.4)] text-white'
              }`}
          >
            <Play className="w-4 h-4" />
            {isSubmitting ? 'Running...' : 'Run Code'}
          </button>
        </div>
      </header>

      {/* Main Content */}
      <PanelGroup id="ide-layout-main-v3" orientation={isMobile ? "vertical" : "horizontal"} className="flex-1 min-h-0">

        {/* Left Panel: Problem Description & Testcases */}
        <Panel defaultSize={30} minSize={20} className="flex flex-col gap-4 glass rounded-2xl p-6 relative min-h-0 overflow-hidden">
          {/* Tabs Header */}
          <div className="flex items-center justify-between border-b border-slate-700/50 pb-3">
            <div className="flex gap-2">
              <button
                onClick={() => setActiveTab('upload')}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${activeTab === 'upload'
                    ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-500/20'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                  }`}
              >
                <ImageIcon className="w-4 h-4" />
                이미지 업로드
              </button>
              <button
                onClick={() => setActiveTab('problem')}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${activeTab === 'problem'
                    ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                  }`}
              >
                <BookOpen className="w-4 h-4" />
                문제 편집
              </button>
              <button
                onClick={() => setActiveTab('testcases')}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${activeTab === 'testcases'
                    ? 'bg-purple-600 text-white shadow-lg shadow-purple-500/20'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                  }`}
              >
                <Layers className="w-4 h-4" />
                테스트케이스 ({testCases.length})
              </button>
            </div>

            {activeTab === 'problem' && (
              <button
                onClick={handleGenerateTestcases}
                disabled={isGeneratingTc}
                className="text-xs px-3 py-1.5 bg-purple-600 hover:bg-purple-500 disabled:bg-slate-700 text-white rounded-lg flex items-center gap-1.5 transition-all shadow-md shadow-purple-900/30 font-medium"
              >
                <Sparkles className={`w-3.5 h-3.5 ${isGeneratingTc ? 'animate-spin' : ''}`} />
                {isGeneratingTc ? 'AI 생성중...' : 'AI 5개 생성'}
              </button>
            )}
          </div>

          {/* Tab 0 Content: Image Upload */}
          {activeTab === 'upload' && (
            <div className={`flex-1 flex flex-col items-center justify-center gap-4 min-h-0 border-2 ${rawOcrText ? 'border-solid border-slate-700 p-4' : 'border-dashed border-slate-700/50 p-8'} rounded-2xl bg-slate-900/30 hover:bg-slate-900/50 transition-colors relative`}>
              {!rawOcrText ? (
                <>
                  <input
                    type="file"
                    accept="image/*"
                    onChange={handleImageUpload}
                    disabled={isOcrLoading}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10 disabled:cursor-not-allowed"
                    title="이미지를 드래그 앤 드롭 하거나 클릭하여 업로드하세요."
                  />

                  <div className="flex flex-col items-center gap-3 text-center z-0 pointer-events-none">
                    {isOcrLoading ? (
                      <>
                        <Loader2 className="w-12 h-12 text-blue-500 animate-spin" />
                        <p className="text-blue-400 font-medium">AI가 이미지에서 글자를 추출하는 중입니다...</p>
                        <p className="text-xs text-slate-500">사진의 크기에 따라 10초 정도 소요될 수 있습니다.</p>
                      </>
                    ) : (
                      <>
                        <div className="w-16 h-16 bg-slate-800 rounded-full flex items-center justify-center shadow-lg shadow-black/20 mb-2">
                          <UploadCloud className="w-8 h-8 text-blue-400" />
                        </div>
                        <p className="text-slate-200 font-semibold text-lg">알고리즘 문제 이미지 업로드</p>
                        <p className="text-sm text-slate-400 max-w-xs">
                          백준, 프로그래머스 등의 문제 화면을 캡처해서 여기에 드래그 앤 드롭 하거나 클릭하여 파일을 선택하세요.
                        </p>
                        <div className="px-4 py-2 bg-blue-600/20 text-blue-400 rounded-lg text-xs font-medium mt-2">
                          AI가 이미지에서 텍스트를 자동 추출합니다 ✨
                        </div>
                      </>
                    )}
                  </div>
                </>
              ) : (
                <div className="w-full h-full flex flex-col gap-4">
                  {/* Top: Image Preview */}
                  <div className="w-full h-[250px] border border-slate-700/50 rounded-xl overflow-hidden bg-slate-900/50 flex items-center justify-center p-2 relative shrink-0">
                    {uploadedImagePreview ? (
                      <img src={uploadedImagePreview} alt="Uploaded Problem" className="object-contain w-full h-full rounded-lg" />
                    ) : (
                      <p className="text-slate-500 text-sm">이미지 미리보기 없음</p>
                    )}
                  </div>
                  
                  {/* Bottom: OCR Text Area */}
                  <div className="flex-1 flex flex-col gap-3">
                    <div className="flex justify-between items-center px-1">
                      <p className="text-slate-200 font-medium text-sm flex items-center gap-2">
                        <Search className="w-4 h-4 text-blue-400" />
                        OCR 추출 결과
                      </p>
                      <span className="text-xs text-slate-500">원한다면 오타를 직접 수정할 수 있습니다.</span>
                    </div>
                    <textarea
                      className="w-full flex-1 bg-slate-900/50 border border-slate-700/50 rounded-xl p-4 text-slate-300 font-mono text-sm resize-none focus:outline-none focus:border-blue-500 transition-all placeholder-slate-600 overflow-y-auto"
                      value={rawOcrText}
                      onChange={(e) => setRawOcrText(e.target.value)}
                      disabled={isRefining}
                    />
                    <div className="flex justify-end gap-2 pt-2">
                      <button
                        onClick={() => { setRawOcrText(''); setUploadedImagePreview(null); }}
                        disabled={isRefining}
                        className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white text-sm rounded-xl transition-all"
                      >
                        🔄 다시 업로드
                      </button>
                      <button
                        onClick={handleRefineFromOcr}
                        disabled={isRefining}
                        className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-xl font-medium transition-all shadow-lg flex items-center gap-2"
                      >
                        <Sparkles className={`w-4 h-4 ${isRefining ? 'animate-spin' : ''}`} />
                        {isRefining ? 'AI가 백준 스타일로 정제 중...' : '✨ 이 텍스트를 백준 스타일로 정제하기'}
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Tab 1 Content: Problem Textarea */}
          {activeTab === 'problem' && (
            <div className="flex-1 flex flex-col gap-2 min-h-0">
              <div className="flex gap-2 items-center">
                <input
                  type="text"
                  className="flex-1 bg-slate-900/70 border border-slate-700/50 rounded-xl px-3 py-1.5 text-slate-200 text-sm focus:outline-none focus:border-blue-500 transition-all placeholder-slate-500 font-medium"
                  placeholder="📌 문제 제목 입력 (예: 두 수의 합)"
                  value={problemTitle}
                  onChange={(e) => setProblemTitle(e.target.value)}
                />
                <button
                  onClick={handleRefineProblem}
                  disabled={isRefining}
                  className="px-3 py-1.5 bg-indigo-600/80 hover:bg-indigo-600 disabled:bg-slate-700 text-white text-xs rounded-xl flex items-center gap-1.5 transition-all shadow-md font-medium shrink-0"
                  title="현재 작성된 거친 텍스트를 AI가 백준 스타일로 깔끔하게 다듬어 줍니다."
                >
                  <Sparkles className={`w-3.5 h-3.5 ${isRefining ? 'animate-spin' : ''}`} />
                  {isRefining ? '정제중...' : 'AI 텍스트 정제'}
                </button>
                <button
                  onClick={handleSaveProblem}
                  disabled={isSavingProblem}
                  className="px-3 py-1.5 bg-blue-600/80 hover:bg-blue-600 disabled:bg-slate-700 text-white text-xs rounded-xl flex items-center gap-1.5 transition-all shadow-md font-medium shrink-0"
                  title="현재 문제 설명과 5개 테스트케이스를 보관함에 저장합니다."
                >
                  <Save className="w-3.5 h-3.5" />
                  {isSavingProblem ? '저장중...' : '문제 저장'}
                </button>
              </div>
              <p className="text-xs text-slate-400">
                문제의 설명, 입력 조건, 출력 조건을 작성해주세요. 상단의 <span className="text-purple-400 font-semibold">'AI 5개 생성'</span> 버튼을 누르면 까다로운 엣지 케이스가 자동 생성됩니다.
              </p>
              <textarea
                className="w-full flex-1 bg-slate-900/50 border border-slate-700/50 rounded-xl p-4 text-slate-300 font-mono text-sm resize-none focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all placeholder-slate-600 overflow-y-auto"
                placeholder="예시: 두 정수 A와 B를 입력받은 다음, A+B를 출력하는 프로그램을 작성하시오.&#10;입력: 공백으로 구분된 두 정수 (1 &lt;= A, B &lt;= 10000)"
                value={problemText}
                onChange={(e) => setProblemText(e.target.value)}
              />
            </div>
          )}
          
          {/* Tab 2 Content: Testcases List */}
          {activeTab === 'testcases' && (
            <div className="flex-1 flex flex-col gap-3 min-h-0 overflow-y-auto pr-1">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-slate-400">Run Code 시 아래 테스트케이스들이 병렬 채점됩니다.</span>
                <button
                  onClick={handleGenerateTestcases}
                  disabled={isGeneratingTc}
                  className="text-xs px-2.5 py-1 bg-purple-600/80 hover:bg-purple-600 disabled:bg-slate-700 text-white rounded-lg flex items-center gap-1 transition-all"
                >
                  <Sparkles className={`w-3 h-3 ${isGeneratingTc ? 'animate-spin' : ''}`} />
                  {isGeneratingTc ? '생성중...' : 'AI 재생성'}
                </button>
              </div>

              {testCases.map((tc, idx) => (
                <div key={idx} className="bg-slate-900/70 border border-slate-700/60 rounded-xl p-3.5 flex flex-col gap-2 transition-all hover:border-slate-600 shadow-sm">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                    <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                      <span className="w-5 h-5 rounded-full bg-slate-800 flex items-center justify-center text-[10px] text-slate-400 font-mono">{idx + 1}</span>
                      테스트케이스 #{idx + 1}
                    </span>
                    <div className="flex items-center gap-2">
                      {tc.status === 'SUCCESS' && (
                        <span className="px-2 py-0.5 rounded-full bg-green-500/20 text-green-400 text-xs flex items-center gap-1 font-medium">
                          <CheckCircle className="w-3 h-3" /> 통과 ({tc.exec_time}s / {tc.memory_kb}KB)
                        </span>
                      )}
                      {tc.status === 'FAIL' && (
                        <span className="px-2 py-0.5 rounded-full bg-red-500/20 text-red-400 text-xs flex items-center gap-1 font-medium">
                          <XCircle className="w-3 h-3" /> 실패 ({tc.exec_time}s / {tc.memory_kb}KB)
                        </span>
                      )}
                      {tc.status === 'RUNNING' && (
                        <span className="px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-400 text-xs flex items-center gap-1 animate-pulse font-medium">
                          🔄 채점중...
                        </span>
                      )}
                      {(!tc.status || tc.status === 'PENDING') && (
                        <span className="px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 text-xs font-medium">대기</span>
                      )}
                      <button
                        onClick={() => handleDeleteTestcase(idx)}
                        className="text-slate-500 hover:text-red-400 p-1 transition-colors"
                        title="삭제"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2 mt-1">
                    <div>
                      <label className="text-[10px] text-slate-400 uppercase font-mono block mb-1">Input</label>
                      <textarea
                        rows={2}
                        value={tc.input}
                        onChange={(e) => handleTestcaseChange(idx, 'input', e.target.value)}
                        placeholder="입력값"
                        className="w-full bg-slate-950/80 border border-slate-800 rounded-lg p-2 text-xs font-mono text-slate-300 resize-none focus:outline-none focus:border-blue-500 transition-colors"
                      />
                    </div>
                    <div>
                      <label className="text-[10px] text-slate-400 uppercase font-mono block mb-1">Expected Output</label>
                      <textarea
                        rows={2}
                        value={tc.expected_output}
                        onChange={(e) => handleTestcaseChange(idx, 'expected_output', e.target.value)}
                        placeholder="기대 출력"
                        className="w-full bg-slate-950/80 border border-slate-800 rounded-lg p-2 text-xs font-mono text-slate-300 resize-none focus:outline-none focus:border-blue-500 transition-colors"
                      />
                    </div>
                  </div>

                  {tc.output && tc.status !== 'SUCCESS' && (
                    <div className="mt-1 p-2 bg-red-950/30 border border-red-900/40 rounded-lg text-xs font-mono text-red-300">
                      <span className="text-[10px] text-red-400 uppercase block mb-0.5">Actual Output:</span>
                      {tc.output.trim() || "(빈 출력)"}
                    </div>
                  )}
                </div>
              ))}

              <button
                onClick={handleAddTestcase}
                className="w-full py-2.5 rounded-xl border border-dashed border-slate-700 hover:border-slate-500 text-slate-400 hover:text-slate-200 text-xs font-medium flex items-center justify-center gap-1.5 transition-all bg-slate-900/30 hover:bg-slate-800/40 mt-1"
              >
                <Plus className="w-3.5 h-3.5" /> 테스트케이스 직접 추가
              </button>
            </div>
          )}
        </Panel>

        <PanelResizeHandle className="w-6 hidden lg:flex bg-slate-800/20 hover:bg-purple-500/10 rounded-full transition-colors cursor-col-resize shrink-0 z-20 items-center justify-center group relative">
            <div className="w-1 h-8 bg-slate-600 rounded-full group-hover:bg-purple-400 transition-colors" />
        </PanelResizeHandle>

        {/* Right Panel: Editor and Terminal */}
        <Panel defaultSize={70} minSize={30} className="flex flex-col min-h-0">
          <PanelGroup id="ide-layout-right-v2" orientation="vertical" className="flex-1 flex min-h-0">
            {/* Editor */}
            <Panel defaultSize={70} minSize={20} className="glass rounded-2xl overflow-hidden flex flex-col border border-slate-700/50 relative">
            <div className="h-10 bg-slate-900/80 flex items-center justify-between px-4 border-b border-slate-800 backdrop-blur-md z-10">
              <div className="flex gap-2">
                <button
                  onClick={() => setActiveCodeTab('mycode')}
                  className={`text-xs px-3 py-1.5 rounded-t-lg transition-colors font-medium border-b-2 ${
                    activeCodeTab === 'mycode' 
                      ? 'bg-slate-800/80 text-blue-400 border-blue-500' 
                      : 'text-slate-500 hover:text-slate-300 border-transparent hover:bg-slate-800/40'
                  }`}
                >
                  내 코드 (My Code)
                </button>
                <button
                  onClick={() => setActiveCodeTab('answer')}
                  className={`text-xs px-3 py-1.5 rounded-t-lg transition-colors font-medium border-b-2 ${
                    activeCodeTab === 'answer' 
                      ? 'bg-slate-800/80 text-emerald-400 border-emerald-500' 
                      : 'text-slate-500 hover:text-slate-300 border-transparent hover:bg-slate-800/40'
                  }`}
                >
                  정답 코드 (Answer Code)
                </button>
              </div>
              <div className="text-xs font-mono text-slate-500">{activeCodeTab === 'answer' ? 'answer.py' : 'solution.py'}</div>
            </div>
            <div className="flex-1 w-full relative">
              <Editor
                height="100%"
                language="python"
                theme="vs-dark"
                value={activeCodeTab === 'answer' ? answerCode : myCode}
                onChange={handleEditorChange}
                options={{
                  minimap: { enabled: false },
                  fontSize: 15,
                  fontFamily: 'var(--font-mono), monospace',
                  padding: { top: 16 },
                  scrollBeyondLastLine: false,
                  smoothScrolling: true,
                  cursorBlinking: "smooth",
                }}
              />
            </div>
          </Panel>

          <PanelResizeHandle className="h-4 w-full flex bg-transparent hover:bg-purple-500/10 transition-colors cursor-row-resize shrink-0 z-20 items-center justify-center group relative my-1">
              <div className="h-1 w-12 bg-slate-700/50 rounded-full group-hover:bg-purple-400 transition-colors" />
          </PanelResizeHandle>

          {/* Terminal / Output */}
          <Panel defaultSize={30} minSize={15} className="glass rounded-2xl p-4 flex flex-col relative">
            <div className="flex items-center justify-between gap-2 mb-3 text-slate-400 pb-2 border-b border-slate-700/50">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4" />
                <span className="text-sm font-medium uppercase tracking-wider">Output Terminal</span>
              </div>
              {status === 'FAIL' && (
                <button
                  onClick={getAiHint}
                  className="text-xs px-3 py-1 bg-purple-600 hover:bg-purple-500 text-white rounded-lg flex items-center gap-1 transition-colors"
                >
                  💡 AI 힌트 받기
                </button>
              )}
            </div>
            <div className="flex-1 bg-[#0a0f1a] rounded-xl p-4 font-mono text-sm overflow-y-auto whitespace-pre-wrap border border-slate-800 text-green-400 shadow-inner">
              {output || 'Run your code to see the output here...'}
            </div>
          </Panel>
          </PanelGroup>
        </Panel>
      </PanelGroup>

      {/* Problem Library Modal */}
      {isProblemModalOpen && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-2xl max-h-[80vh] flex flex-col shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-slate-900/50">
              <h2 className="text-lg font-bold flex items-center gap-2 text-slate-100">
                <FolderOpen className="w-5 h-5 text-purple-400" />
                📚 문제 보관함
              </h2>
              <button
                onClick={() => setIsProblemModalOpen(false)}
                className="text-slate-400 hover:text-slate-200 p-1 rounded-lg hover:bg-slate-800 transition-colors text-sm font-semibold px-2.5 py-1"
              >
                ✕
              </button>
            </div>
            <div className="p-5 flex-1 overflow-y-auto flex flex-col gap-3">
              {isLoadingProblems ? (
                <div className="text-center py-12 text-slate-400 flex flex-col items-center gap-3">
                  <div className="w-6 h-6 rounded-full border-2 border-t-purple-500 border-purple-200 animate-spin" />
                  문제 목록을 불러오는 중...
                </div>
              ) : savedProblems.length === 0 ? (
                <div className="text-center py-12 text-slate-500 flex flex-col items-center gap-2">
                  <Bookmark className="w-10 h-10 text-slate-600 mb-1" />
                  <p>보관함에 저장된 문제가 없습니다.</p>
                  <p className="text-xs text-slate-600">문제 설명란에서 [문제 저장] 버튼을 눌러 문제를 보관해보세요!</p>
                </div>
              ) : (
                savedProblems.map((prob) => (
                  <div
                    key={prob.id}
                    onClick={() => handleLoadProblem(prob.id)}
                    className="bg-slate-800/50 hover:bg-slate-800 border border-slate-700/60 hover:border-purple-500/50 rounded-xl p-4 flex items-center justify-between cursor-pointer transition-all group"
                  >
                    <div className="flex flex-col gap-1 pr-4 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-slate-200 group-hover:text-purple-300 transition-colors truncate">
                          {prob.title || '제목 없는 문제'}
                        </span>
                        <span className="text-[10px] bg-purple-900/50 text-purple-300 px-2 py-0.5 rounded-full border border-purple-700/40 shrink-0">
                          테스트케이스 {prob.testCases?.length || 0}개
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 line-clamp-2">
                        {prob.description || '설명 없음'}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-blue-600/20 text-blue-400 group-hover:bg-blue-600 group-hover:text-white transition-all">
                        불러오기
                      </span>
                      <button
                        onClick={(e) => handleDeleteProblem(prob.id, e)}
                        className="p-1.5 text-slate-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                        title="삭제"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
            <div className="p-4 border-t border-slate-800 bg-slate-900/50 text-right">
              <button
                onClick={() => setIsProblemModalOpen(false)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-sm font-medium transition-colors"
              >
                닫기
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
