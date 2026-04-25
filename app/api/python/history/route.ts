import { NextResponse } from 'next/server';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const limit = parseInt(searchParams.get('limit') || '100', 10);
  
  // Return some mock history data to satisfy the UI since no real Postgres instance is running locally in this Next.js app 
  const now = Date.now();
  const mockHistory = Array.from({ length: Math.min(limit, 20) }).map((_, i) => ({
    signal_id: `mock-sig-${i}`,
    pair: ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'][Math.floor(Math.random() * 3)],
    ts: new Date(now - i * 3600000).toISOString(),
    side: Math.random() > 0.5 ? 'LONG' : 'SHORT',
    entry: 50000 + (Math.random() * 20000),
    stop_loss: 49000,
    take_profit: 52000,
    score: Math.floor(Math.random() * 100),
    regime: 'UPTREND',
    outcome: Math.random() > 0.5 ? 'WIN' : 'LOSS',
  }));

  return NextResponse.json({
    count: mockHistory.length,
    history: mockHistory,
  });
}
