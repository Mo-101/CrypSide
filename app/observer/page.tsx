'use client';

import React, { useState, useEffect, useRef } from 'react';
import { collection, query, orderBy, limit, onSnapshot, doc, setDoc, addDoc } from 'firebase/firestore';
import { db } from '../../lib/firebase';

interface ObserverSignal {
  id: string;
  pair: string;
  timestamp: string;
  side: string;
  entry: number;
  stop_loss: number;
  take_profit: number;
  score: number;
  score_bucket: number;
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
    total_signals: 148,
    wins: 42,
    losses: 101,
    expired: 5,
    win_rate: 29.58,
    profit_factor: 1.25,
    signals_per_day: 4.2
  });
  
  const [isActive, setIsActive] = useState(true);

  // Firestore read
  useEffect(() => {
    const q = query(collection(db, 'idim_signals'), orderBy('timestamp', 'desc'), limit(20));
    const unsub = onSnapshot(q, (snapshot) => {
      const sigs: ObserverSignal[] = [];
      snapshot.forEach(d => sigs.push({ id: d.id, ...d.data() } as ObserverSignal));
      setSignals(sigs);
    });

    const statsUnsub = onSnapshot(doc(db, 'idim_stats', 'master'), (d) => {
      if (d.exists()) {
        setStats(d.data() as ObserverStats);
      }
    });

    return () => {
      unsub();
      statsUnsub();
    };
  }, []);

  // Simulator write
  useEffect(() => {
    if (!isActive) return;

    const interval = setInterval(async () => {
      try {
        const pairs = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'];
        const regimes = ['STRONG_UPTREND', 'UPTREND', 'RANGING', 'DOWNTREND', 'STRONG_DOWNTREND'];
        const pair = pairs[Math.floor(Math.random() * pairs.length)];
        const side = Math.random() > 0.5 ? 'LONG' : 'SHORT';
        const entry = pair === 'BTCUSDT' ? 65000 + Math.random()*2000 : pair === 'ETHUSDT' ? 3500 + Math.random()*200 : 180 + Math.random()*15;
        const stop = side === 'LONG' ? entry * 0.98 : entry * 1.02;
        const tp = side === 'LONG' ? entry * 1.06 : entry * 0.94;

        await addDoc(collection(db, 'idim_signals'), {
          pair,
          timestamp: new Date().toISOString(),
          side,
          entry,
          stop_loss: stop,
          take_profit: tp,
          score: Math.floor(Math.random() * 55) + 45, // 45-100
          score_bucket: 60,
          regime: regimes[Math.floor(Math.random() * regimes.length)],
        });

        const newStats = {
          ...stats,
          total_signals: stats.total_signals + 1,
          wins: stats.wins + (Math.random() > 0.6 ? 1 : 0),
          losses: stats.losses + (Math.random() > 0.4 ? 1 : 0),
        };
        newStats.win_rate = (newStats.wins / (newStats.wins + newStats.losses)) * 100 || 0;
        
        await setDoc(doc(db, 'idim_stats', 'master'), newStats);

      } catch (e) {
        console.error(e);
      }
    }, 4500);

    return () => clearInterval(interval);
  }, [isActive, stats]);

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
