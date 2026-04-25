'use client';

import React, { useState, useEffect, useRef } from 'react';

interface ObserverSignal {
  id: string;
  pair: string;
  timestamp: string;
  side: string;
  entry: number;
  stop_loss: number;
  take_profit: number;
  score: number;
  regime: string;
  outcome?: string;
  r_multiple?: number;
}

interface ObserverStats {
  total_signals: number;
  wins: number;
  losses: number;
  expired: number;
  win_rate: number;
  profit_factor: number;
  signals_per_day: number;
}

export default function IdimIkangObserver() {
  const [signals, setSignals] = useState<ObserverSignal[]>([]);
  const [stats, setStats] = useState<ObserverStats>({
    total_signals: 0,
    wins: 0,
    losses: 0,
    expired: 0,
    win_rate: 0,
    profit_factor: 0,
    signals_per_day: 0
  });
  
  const [isActive, setIsActive] = useState(true);
  const [apiConnected, setApiConnected] = useState(false);

  // Fetch initial history
  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const res = await fetch('/api/python/history?limit=20');
        if (res.ok) {
          const data = await res.json();
          const mapped = data.history.map((d: any) => ({
            id: String(d.signal_id || d.id),
            pair: d.pair,
            timestamp: d.ts,
            side: d.side,
            entry: d.entry,
            stop_loss: d.stop_loss,
            take_profit: d.take_profit,
            score: d.score,
            regime: d.regime,
            outcome: d.outcome,
            r_multiple: d.r_multiple
          }));
          setSignals(mapped);
          
          // Calculate stats locally from history for now
          setStats(prev => ({
            ...prev,
            total_signals: data.history.length,
          }));
        }
      } catch (e) {
        console.error("Failed to fetch history", e);
      }
    };
    fetchHistory();
  }, []);

  // WebSocket connection
  useEffect(() => {
    if (!isActive) return;

    let ws: WebSocket;
    const connect = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/api/python/ws`;
      ws = new WebSocket(wsUrl);
      
      ws.onopen = () => setApiConnected(true);
      ws.onclose = () => {
        setApiConnected(false);
        // Retry connection
        if (isActive) setTimeout(connect, 3000);
      };
      
      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === 'new_signal') {
            const sig = payload.data;
            const newSig: ObserverSignal = {
                id: String(sig.signal_id || sig.id),
                pair: sig.pair,
                timestamp: sig.ts,
                side: sig.side,
                entry: sig.entry,
                stop_loss: sig.stop_loss,
                take_profit: sig.take_profit,
                score: sig.score,
                regime: sig.regime
            };
            setSignals(prev => [newSig, ...prev].slice(0, 50));
            setStats(prev => ({ ...prev, total_signals: prev.total_signals + 1 }));
          }
        } catch (e) {
          console.error("WS parse error", e);
        }
      };
    };

    connect();

    return () => {
      if (ws) {
        ws.onclose = null;
        ws.close();
      }
    };
  }, [isActive]);

  return (
    <div className="flex-1 p-6 flex flex-col gap-6">
      <header className="flex justify-between items-end mb-4 pb-4 border-b border-[#222]">
        <div>
          <h1 className="text-3xl font-black tracking-tighter uppercase mb-2">Idim Ikang Observer</h1>
          <p className="text-[10px] uppercase tracking-widest font-bold text-gray-500">Live baseline-aligned sovereign scanning</p>
        </div>
        <div className="flex gap-4">
          <button 
            onClick={() => setIsActive(!isActive)}
            className={`px-6 py-2 text-xs font-black uppercase tracking-tighter ${isActive ? 'bg-red-900/40 text-red-400 border border-red-900/60' : 'bg-white text-black'} transition-colors`}
          >
            {isActive ? 'KILL SCANNER' : 'ACTIVATE SCANNER'}
          </button>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        
        {/* Stats Column */}
        <div className="lg:col-span-1 flex flex-col gap-6">
          <div className="bg-[#111] p-6 rounded border border-[#222]">
            <h2 className="text-[10px] uppercase font-bold tracking-widest text-gray-500 mb-6">Observer Status</h2>
            <div className="space-y-4">
               <div>
                 <span className="block text-[10px] text-gray-500 uppercase tracking-widest">Scanner State</span>
                 <span className={`font-black ${isActive ? 'text-green-500' : 'text-red-500'}`}>{isActive ? 'RUNNING' : 'STOPPED'}</span>
               </div>
               <div>
                 <span className="block text-[10px] text-gray-500 uppercase tracking-widest">Logic Version</span>
                 <span className="font-mono text-cyan-400 text-xs">v1.0-baseline-observer</span>
               </div>
               <div>
                 <span className="block text-[10px] text-gray-500 uppercase tracking-widest">Config Version</span>
                 <span className="font-mono text-cyan-400 text-xs">v1.2-top30-futures</span>
               </div>
            </div>
          </div>

          <div className="bg-[#111] p-6 rounded border border-[#222]">
             <h2 className="text-[10px] uppercase font-bold tracking-widest text-gray-500 mb-6">Aggregated Metrics</h2>
             <div className="grid grid-cols-2 gap-4 gap-y-6">
                <div>
                  <span className="block text-[10px] text-gray-500 uppercase tracking-widest">Total Sigs</span>
                  <span className="text-xl font-black">{stats.total_signals}</span>
                </div>
                <div>
                  <span className="block text-[10px] text-gray-500 uppercase tracking-widest">Win Rate</span>
                  <span className="text-xl font-black text-white">{stats.win_rate.toFixed(2)}%</span>
                </div>
                <div>
                  <span className="block text-[10px] text-gray-500 uppercase tracking-widest">Profit Factor</span>
                  <span className="text-xl font-black text-green-400">{stats.profit_factor.toFixed(2)}</span>
                </div>
                <div>
                  <span className="block text-[10px] text-gray-500 uppercase tracking-widest">Sigs / Day</span>
                  <span className="text-xl font-black text-cyan-400">{stats.signals_per_day.toFixed(1)}</span>
                </div>
             </div>
          </div>
        </div>

        {/* Signals Feed */}
        <div className="lg:col-span-3 flex flex-col gap-6">
           <div className="bg-[#111] border border-[#222] rounded flex-1 flex flex-col">
              <div className="p-4 border-b border-[#222]">
                 <h2 className="text-[10px] uppercase font-bold tracking-widest text-gray-500">Live Signals Target Feed</h2>
              </div>
              <div className="p-0 overflow-x-auto text-xs">
                 <table className="w-full text-left font-mono whitespace-nowrap">
                    <thead className="bg-[#1a1a1a] text-gray-500 uppercase tracking-widest text-[9px]">
                       <tr>
                          <th className="px-4 py-3 font-normal">Timestamp</th>
                          <th className="px-4 py-3 font-normal">Pair</th>
                          <th className="px-4 py-3 font-normal">Side</th>
                          <th className="px-4 py-3 font-normal text-right">Entry</th>
                          <th className="px-4 py-3 font-normal text-right">SL / TP</th>
                          <th className="px-4 py-3 font-normal text-right">Score</th>
                          <th className="px-4 py-3 font-normal">Regime</th>
                       </tr>
                    </thead>
                    <tbody className="divide-y divide-[#222]">
                       {signals.map((sig) => (
                         <tr key={sig.id} className="hover:bg-[#1a1a1a] transition-colors">
                           <td className="px-4 py-3 text-gray-400">{new Date(sig.timestamp).toLocaleTimeString()}</td>
                           <td className="px-4 py-3 font-bold text-white">{sig.pair}</td>
                           <td className={`px-4 py-3 font-bold ${sig.side === 'LONG' ? 'text-green-500' : 'text-red-500'}`}>{sig.side}</td>
                           <td className="px-4 py-3 text-right text-gray-200">{sig.entry.toFixed(2)}</td>
                           <td className="px-4 py-3 text-right text-gray-500">
                             <span className="text-red-400/80">{sig.stop_loss.toFixed(2)}</span> / <span className="text-green-400/80">{sig.take_profit.toFixed(2)}</span>
                           </td>
                           <td className="px-4 py-3 text-right text-cyan-400">{sig.score}</td>
                           <td className="px-4 py-3 text-gray-400 text-[10px]">{sig.regime}</td>
                         </tr>
                       ))}
                       {signals.length === 0 && (
                         <tr>
                            <td colSpan={7} className="px-4 py-12 text-center text-gray-600 tracking-widest">WAITING FOR NETWORK SIGNAL...</td>
                         </tr>
                       )}
                    </tbody>
                 </table>
              </div>
           </div>
        </div>

      </div>
    </div>
  );
}
