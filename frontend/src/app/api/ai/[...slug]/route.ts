import { NextRequest, NextResponse } from 'next/server';

export const maxDuration = 60; // Vercel Hobby tier maximum timeout (60 seconds)

export async function POST(req: NextRequest, { params }: { params: Promise<{ slug: string[] }> }) {
  const { slug } = await params;
  const path = slug.join('/');
  const aiApiUrl = process.env.NEXT_PUBLIC_AI_API_URL || 'http://localhost:8000';
  
  try {
    const contentType = req.headers.get('content-type') || 'application/json';
    const authHeader = req.headers.get('authorization') || '';
    
    // We must read the body as a buffer/blob or pass the stream
    // Using arrayBuffer is safe for both JSON and FormData (multipart)
    const bodyBuffer = await req.arrayBuffer();

    const response = await fetch(`${aiApiUrl}/api/ai/${path}`, {
      method: 'POST',
      headers: {
        'Authorization': authHeader,
        'Content-Type': contentType,
        'ngrok-skip-browser-warning': 'true',
      },
      body: bodyBuffer,
    });

    // Determine how to parse the response based on content-type from AI server
    const resContentType = response.headers.get('content-type') || '';
    if (resContentType.includes('application/json')) {
      const data = await response.json();
      return NextResponse.json(data, { status: response.status });
    } else {
      const text = await response.text();
      return new NextResponse(text, { status: response.status, headers: { 'Content-Type': resContentType } });
    }
  } catch (error: any) {
    console.error("AI Proxy Error:", error);
    return NextResponse.json({ error: "AI Server connection failed or timed out." }, { status: 500 });
  }
}
