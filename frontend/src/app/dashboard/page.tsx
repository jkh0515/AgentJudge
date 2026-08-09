"use client";

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { LayoutDashboard, LogOut, Code2, Clock, CheckCircle, XCircle } from 'lucide-react';

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<{ email: string; username: string } | null>(null);
  const [submissions, setSubmissions] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('token');
    const userData = localStorage.getItem('user');

    if (!token || !userData) {
      router.push('/login');
      return;
    }

    setUser(JSON.parse(userData));

    // Fetch submissions
    const fetchSubmissions = async () => {
      try {
        const response = await fetch(`/api/users/me/submissions`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
        
        if (response.ok) {
          const data = await response.json();
          setSubmissions(data);
        } else if (response.status === 401) {
          // Token expired or invalid
          localStorage.removeItem('token');
          localStorage.removeItem('user');
          router.push('/login');
        }
      } catch (err) {
        console.error("Failed to fetch submissions", err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchSubmissions();
  }, [router]);

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    router.push('/login');
  };

  if (isLoading) {
    return <div className="min-h-screen bg-[#0f172a] text-slate-200 flex items-center justify-center">Loading...</div>;
  }

  return (
    <div className="min-h-screen bg-[#0f172a] text-slate-200 p-4 md:p-6 flex flex-col h-screen">
      {/* Header */}
      <header className="flex justify-between items-center mb-6 glass px-6 py-4 rounded-2xl">
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2 cursor-pointer" onClick={() => router.push('/')}>
          <span className="gradient-text">Agent</span>Judge
        </h1>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-800/50 border border-slate-700">
            <span className="text-sm font-medium">{user?.username} ({user?.email})</span>
          </div>
          <button 
            onClick={() => router.push('/')}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-700 hover:bg-slate-600 transition-colors"
          >
            <Code2 className="w-4 h-4" />
            Editor
          </button>
          <button 
            onClick={handleLogout}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-red-600 hover:bg-red-500 text-white transition-colors"
          >
            <LogOut className="w-4 h-4" />
            Logout
          </button>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 flex flex-col gap-6 min-h-0">
        <div className="glass rounded-2xl p-6 flex flex-col h-full">
          <div className="flex items-center gap-2 mb-6 pb-4 border-b border-slate-700/50">
            <LayoutDashboard className="w-6 h-6 text-blue-400" />
            <h2 className="text-2xl font-semibold">My Submissions</h2>
          </div>
          
          <div className="flex-1 overflow-y-auto pr-2">
            {submissions.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-slate-500">
                <Code2 className="w-12 h-12 mb-4 opacity-20" />
                <p>No submissions yet.</p>
                <button onClick={() => router.push('/')} className="mt-4 text-blue-400 hover:underline">Go solve some problems!</button>
              </div>
            ) : (
              <div className="space-y-4">
                {submissions.map((sub, idx) => (
                  <div key={idx} className="bg-slate-900/50 border border-slate-800 rounded-xl p-5 flex flex-col gap-3 transition-colors hover:bg-slate-800/50">
                    <div className="flex justify-between items-center">
                      <div className="flex items-center gap-3">
                        <span className="text-lg font-medium">Problem #{sub.problemId}</span>
                        <span className="px-2 py-1 text-xs rounded-md bg-slate-800 border border-slate-700">{sub.language}</span>
                      </div>
                      <div className="flex items-center gap-2 font-medium">
                        {sub.status === 'SUCCESS' && <><CheckCircle className="w-5 h-5 text-green-400"/> <span className="text-green-400">SUCCESS</span></>}
                        {sub.status === 'FAIL' && <><XCircle className="w-5 h-5 text-red-400"/> <span className="text-red-400">FAIL</span></>}
                        {sub.status === 'TIMEOUT' && <><Clock className="w-5 h-5 text-yellow-400"/> <span className="text-yellow-400">TIMEOUT</span></>}
                        {sub.status === 'ERROR' && <span className="text-red-500">ERROR</span>}
                        {sub.status === 'PENDING' && <span className="text-slate-400">PENDING</span>}
                        {sub.status === 'PROCESSING' && <span className="text-blue-400">PROCESSING</span>}
                      </div>
                    </div>
                    {sub.resultOutput && (
                      <div className="bg-[#0a0f1a] p-3 rounded-lg text-xs font-mono text-slate-400 whitespace-pre-wrap max-h-32 overflow-y-auto">
                        {sub.resultOutput}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
