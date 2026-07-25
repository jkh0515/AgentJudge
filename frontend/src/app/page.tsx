"use client";

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Editor from '@monaco-editor/react';
import { Play, Terminal, BookOpen, CheckCircle, XCircle, Clock, LayoutDashboard, LogOut, Plus, Trash2, Sparkles, Layers, Bookmark, Save, FolderOpen } from 'lucide-react';

interface TestCase {
  input: string;
  expected_output: string;
  status?: 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAIL' | 'ERROR' | 'TIMEOUT';
  output?: string;
  exec_time?: number;
}

export default function JudgePage() {
  const router = useRouter();
  const [code, setCode] = useState<string>('import sys\ndata = sys.stdin.read().strip().split()\nprint(int(data[0]) + int(data[1]))');
  const [problemText, setProblemText] = useState<string>('');
  const [language, setLanguage] = useState<string>('python');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [output, setOutput] = useState<string>('');
  const [status, setStatus] = useState<string>('READY');
  const [user, setUser] = useState<{ email: string; username: string } | null>(null);

  // Testcase & Tab management
  const [activeTab, setActiveTab] = useState<'problem' | 'testcases'>('problem');
  const [isGeneratingTc, setIsGeneratingTc] = useState<boolean>(false);
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
          code: code,
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
          setCode(data.code);
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
        .then(res => res.json())
        .then(data => {
          if (data && data.problemText !== undefined) {
            setProblemText(data.problemText);
            if (data.code) setCode(data.code);
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
      setCode(value);
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
    setOutput(prev => prev + '\n[🤖 AI] 문제 분석 및 엣지 테스트케이스 5개 생성 중...\n');
    try {
      const response = await fetch(`/api/ai/testcases`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          problem_text: problemText,
        }),
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "테스트케이스 생성 실패");

      if (data && data.testcases && Array.isArray(data.testcases)) {
        setTestCases(data.testcases.map((tc: any) => ({
          input: tc.input || "",
          expected_output: tc.expected_output || tc.expectedOutput || "",
          status: 'PENDING'
        })));
        setOutput(prev => prev + `[🤖 AI] 엣지 테스트케이스 ${data.testcases.length}개 생성 완료!\n`);
      }
    } catch (error: any) {
      setOutput(prev => prev + `[🤖 AI Error] ${error.message}\n`);
      alert("AI 테스트케이스 생성에 실패했습니다: " + error.message);
    } finally {
      setIsGeneratingTc(false);
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
    if (!code.trim()) {
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
          code: code,
          language: language,
          testCases: testCases.map(tc => ({
            input: tc.input,
            expected_output: tc.expected_output
          }))
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to submit code');
      }

      const submissionId = data.submission_id;
      setOutput(prev => prev + `Submission successful! (ID: ${submissionId})\nParallel workers executing ${testCases.length} test cases...\n`);

      const eventSource = new EventSource(`/api/submissions/${submissionId}/stream`);

      eventSource.addEventListener('connect', (e) => {
        setOutput(prev => prev + `[Connected] ${e.data}\nWaiting for worker pool...\n`);
      });

      eventSource.addEventListener('testcase_result', (e) => {
        const result = JSON.parse(e.data);
        setTestCases(prev => prev.map((tc, idx) => {
          if (idx === result.index - 1) {
            return {
              ...tc,
              status: result.status === 'SUCCESS' ? 'SUCCESS' : 'FAIL',
              output: result.output,
              exec_time: result.exec_time
            };
          }
          return tc;
        }));
      });

      eventSource.addEventListener('judge_result', (e) => {
        const result = JSON.parse(e.data);
        setStatus(result.status);

        let formattedOutput = `\n[Final Result: ${result.status}]\n`;
        if (result.output) {
          formattedOutput += `${result.output}\n`;
        }

        setOutput(prev => prev + formattedOutput);

        eventSource.close();
        setIsSubmitting(false);
      });

      eventSource.onerror = (e) => {
        setOutput(prev => prev + '\n[Error] Connection to stream lost.\n');
        eventSource.close();
        setIsSubmitting(false);
        if (status === 'PENDING') {
          setStatus('ERROR');
        }
      };

    } catch (error: any) {
      setOutput(prev => prev + `\n[Error] ${error.message}\n`);
      setStatus('ERROR');
      setIsSubmitting(false);
    }
  };

  const getAiHint = async () => {
    const token = localStorage.getItem('token');
    setOutput(prev => prev + '\n[🤖 AI] 분석 중... (시간이 조금 걸릴 수 있습니다)\n');
    try {
      const response = await fetch(`/api/ai/hint`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          problemText: problemText,
          failedCode: code,
        }),
      });

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
          <span className="gradient-text">Vacation</span> Judge
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
      <div className="flex-1 flex flex-col lg:flex-row gap-6 min-h-0">

        {/* Left Panel: Problem Description & Testcases */}
        <div className="lg:w-1/3 flex flex-col gap-4 glass rounded-2xl p-6 relative min-h-0 overflow-hidden">
          {/* Tabs Header */}
          <div className="flex items-center justify-between border-b border-slate-700/50 pb-3">
            <div className="flex gap-2">
              <button
                onClick={() => setActiveTab('problem')}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                  activeTab === 'problem'
                    ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                <BookOpen className="w-4 h-4" />
                문제 설명
              </button>
              <button
                onClick={() => setActiveTab('testcases')}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                  activeTab === 'testcases'
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

          {/* Tab 1 Content: Problem Textarea */}
          {activeTab === 'problem' ? (
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
          ) : (
            /* Tab 2 Content: Testcases List */
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
                          <CheckCircle className="w-3 h-3" /> 통과 ({tc.exec_time}s)
                        </span>
                      )}
                      {tc.status === 'FAIL' && (
                        <span className="px-2 py-0.5 rounded-full bg-red-500/20 text-red-400 text-xs flex items-center gap-1 font-medium">
                          <XCircle className="w-3 h-3" /> 실패 ({tc.exec_time}s)
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
        </div>

        {/* Right Panel: Editor and Terminal */}
        <div className="lg:w-2/3 flex flex-col gap-6 min-h-0">

          {/* Editor */}
          <div className="flex-1 glass rounded-2xl overflow-hidden flex flex-col border border-slate-700/50 relative">
            <div className="h-10 bg-slate-900/80 flex items-center justify-between px-4 border-b border-slate-800 backdrop-blur-md z-10">
              <div className="flex gap-2">
                <div className="w-3 h-3 rounded-full bg-red-500/80"></div>
                <div className="w-3 h-3 rounded-full bg-yellow-500/80"></div>
                <div className="w-3 h-3 rounded-full bg-green-500/80"></div>
              </div>
              <div className="text-xs font-mono text-slate-400 absolute left-1/2 -translate-x-1/2">solution.py</div>
            </div>
            <div className="flex-1 w-full relative">
              <Editor
                height="100%"
                language="python"
                theme="vs-dark"
                value={code}
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
          </div>

          {/* Terminal / Output */}
          <div className="h-64 glass rounded-2xl p-4 flex flex-col relative">
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
          </div>

        </div>
      </div>

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
