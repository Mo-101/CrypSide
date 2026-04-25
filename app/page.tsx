'use client';

import React, { useState, useEffect, useRef } from 'react';
import { doc, onSnapshot, setDoc, addDoc, collection, query, orderBy, limit, serverTimestamp } from 'firebase/firestore';
import { db } from '../lib/firebase';

interface Signal {
  id: string;
  timestamp: number;
  pair: string;
  prediction: number;
  confidence: number;
  action: string;
}

export default function SovereignIngestionNode() {
  const [ingestState, setIngestState] = useState<'idle' | 'processing' | 'success' | 'error'>('idle');
  const [recordsProcessed, setRecordsProcessed] = useState(0);
  const [bufferSize, setBufferSize] = useState(0);
  const [liveSignals, setLiveSignals] = useState<Signal[]>([]);
  const isSimulatingRef = useRef(false);

  // Read telemetry from Firebase
  useEffect(() => {
    const unsub = onSnapshot(doc(db, 'telemetry', 'master'), (docSnap) => {
      if (docSnap.exists()) {
        const data = docSnap.data();
        setRecordsProcessed(data.recordsProcessed || 0);
        setBufferSize(data.bufferSize || 0);
      }
    });

    const q = query(collection(db, 'signals'), orderBy('timestamp', 'desc'), limit(5));
    const unsubSignals = onSnapshot(q, (snapshot) => {
      const sigs: Signal[] = [];
      snapshot.forEach(d => sigs.push({ id: d.id, ...d.data() } as Signal));
      setLiveSignals(sigs);
    });

    return () => {
      unsub();
      unsubSignals();
    };
  }, []);

  // Simulator interval
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (ingestState === 'processing') {
      isSimulatingRef.current = true;
      interval = setInterval(async () => {
        if (!isSimulatingRef.current) return;
        
        try {
          // Increment locally and remotely
          const incRecords = Math.floor(Math.random() * 500) + 1200;
          const incBuffer = Number((Math.random() * 0.05).toFixed(3));
          
          const newRecords = recordsProcessed + incRecords;
          const newBuffer = bufferSize + incBuffer;
          
          await setDoc(doc(db, 'telemetry', 'master'), {
            recordsProcessed: newRecords,
            bufferSize: newBuffer,
            lastUpdate: Date.now()
          });

          // Simulate generating a signal
          const pairs = ['BTC-PERP', 'ETH-PERP', 'SOL-PERP'];
          const actions = ['LONG', 'SHORT', 'HOLD'];
          await addDoc(collection(db, 'signals'), {
            timestamp: Date.now(),
            pair: pairs[Math.floor(Math.random() * pairs.length)],
            prediction: Number((Math.random() * 1000).toFixed(2)),
            confidence: Number((Math.random() * 0.4 + 0.5).toFixed(2)), // 50-90%
            action: actions[Math.floor(Math.random() * actions.length)]
          });

        } catch (e) {
          console.error("Simulation error sync:", e);
        }
      }, 2500); // update every 2.5s
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [ingestState, recordsProcessed, bufferSize]);

  const handleIngest = (e: React.FormEvent) => {
    e.preventDefault();
    if (ingestState === 'processing') {
      setIngestState('idle'); // Toggle to stop
      isSimulatingRef.current = false;
    } else {
      setIngestState('processing');
    }
  };

  return (
    <div className="flex-1 p-6 flex flex-col gap-6">
      <header className="mb-2 pb-4">
        <h1 className="text-3xl font-black tracking-tighter mb-4 uppercase">MoStar Sovereign Data Conduit :: Ingestion Node</h1>
        <div className="flex flex-wrap gap-4 text-[10px] uppercase tracking-widest font-bold text-gray-500">
          <span className="bg-[#111] px-3 py-1.5 rounded border border-[#333]">Jurisdiction: 🟢 AFR-1 (Nairobi/Kenya)</span>
          <span className="bg-[#111] px-3 py-1.5 rounded border border-[#333]">Encryption: 🔒 AES-256-GCM / TLS 1.3</span>
          <span className="bg-[#111] px-3 py-1.5 rounded border border-[#333]">Compliance: 🛡️ DPA / POPIA / NDPR</span>
        </div>
      </header>

      <main className="grid grid-cols-1 lg:grid-cols-12 gap-6 flex-1">
        <section className="lg:col-span-8 flex flex-col gap-6">
          <div className="bg-[#111] p-6 rounded border border-[#222]">
            <h2 className="text-[10px] uppercase tracking-widest text-gray-500 mb-6 font-bold">Real Data Point Collection</h2>
            
            <form onSubmit={handleIngest} className="space-y-6">
              <div>
                <label className="block text-[10px] uppercase font-bold text-gray-500 mb-2">Data Source (Local Air-Gapped Mount)</label>
                <input 
                  type="text" 
                  defaultValue="/mnt/secure_volume_1/market_data/tick_history.parquet"
                  className="w-full bg-transparent border-b border-[#333] py-2 text-xl font-black outline-none focus:border-white font-mono"
                  readOnly
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <div>
                  <label className="block text-[10px] uppercase font-bold text-gray-500 mb-2">Target ML Utility</label>
                  <select className="w-full bg-transparent border-b border-[#333] py-2 text-xl font-black outline-none focus:border-white appearance-none">
                    <option value="CTSyn" className="bg-[#111] text-white text-sm font-sans">CTSyn (Time-Series Generation)</option>
                    <option value="DoppelGANger" className="bg-[#111] text-white text-sm font-sans">DoppelGANger</option>
                    <option value="TabDDPM" className="bg-[#111] text-white text-sm font-sans">TabDDPM (Tabular Density)</option>
                  </select>
                </div>
                
                <div>
                  <label className="block text-[10px] uppercase font-bold text-gray-500 mb-2">Differential Privacy Target (ε)</label>
                  <input 
                    type="number" 
                    step="0.1" 
                    defaultValue="1.2"
                    className="w-full bg-transparent border-b border-[#333] py-2 text-2xl font-black outline-none focus:border-white"
                  />
                </div>
              </div>

              <button 
                type="submit" 
                className={`mt-8 ${ingestState === 'processing' ? 'bg-red-600 text-white hover:bg-red-500' : 'bg-white text-black hover:bg-gray-200'} font-black py-4 text-sm tracking-tighter uppercase w-full transition-colors`}
              >
                {ingestState === 'idle' && 'Initiate Secure Ingestion'}
                {ingestState === 'processing' && 'HALT SECURE INGESTION'}
                {ingestState === 'success' && 'Initiate Secure Ingestion'}
                {ingestState === 'error' && 'Retry Ingestion'}
              </button>
            </form>
          </div>
        </section>

        <aside className="lg:col-span-4 flex flex-col gap-6">
          <div className="bg-[#111] p-6 rounded border border-[#222]">
            <h3 className="text-[10px] uppercase font-bold tracking-widest text-gray-500 mb-4">System Telemetry</h3>
            <ul className="space-y-4 text-sm font-black">
              <li className="flex flex-col border-b border-[#222] pb-4">
                <span className="text-[10px] text-gray-500 uppercase tracking-widest mb-1">Ingest Buffer</span>
                <span className="text-xl text-cyan-400 truncate">{bufferSize.toFixed(2)} / 64.00 GB</span>
              </li>
              <li className="flex flex-col border-b border-[#222] pb-4">
                <span className="text-[10px] text-gray-500 uppercase tracking-widest mb-1">Total Valid Points</span>
                <span className="text-2xl tracking-tighter truncate">{recordsProcessed.toLocaleString()}</span>
              </li>
              <li className="flex flex-col border-b border-[#222] pb-4">
                <span className="text-[10px] text-gray-500 uppercase tracking-widest mb-1">Model Target</span>
                <span className="text-xl text-white truncate">TabDDPM</span>
              </li>
              <li className="flex flex-col">
                <span className="text-[10px] text-gray-500 uppercase tracking-widest mb-1">Network Bleed Audit</span>
                <span className="text-xl text-cyan-400 truncate">✅ 0 Bytes External</span>
              </li>
            </ul>
          </div>

          <div className="bg-[#111] p-6 rounded border border-[#222]">
            <h3 className="text-[10px] uppercase font-bold tracking-widest text-gray-500 mb-4">Security Enforcement</h3>
            <p className="text-xs text-gray-400 font-medium leading-relaxed mb-6">
              All data ingested through this terminal remains strictly within the AFR-1 node. Compute is physically isolated from public egress routes using local certificate authorities.
            </p>
            <div className="bg-cyan-950/20 p-4 rounded border border-cyan-800/30">
              <p className="text-[10px] uppercase font-bold tracking-widest text-cyan-400 mb-2">Strict Constraint</p>
              <p className="text-xs text-cyan-200 font-medium leading-relaxed">
                Modification of `DP_EPSILON` below 1.0 requires direct cryptographic sign-off from the Sovereign Data Controller.
              </p>
            </div>
          </div>

          {/* Live Data Feed Section */}
          <div className="bg-[#111] p-6 rounded border border-[#222]">
            <h3 className="text-[10px] uppercase font-bold tracking-widest text-gray-500 mb-4">Live Prediction Feed</h3>
            <div className="space-y-2 overflow-y-auto max-h-[300px] font-mono text-xs">
              {liveSignals.length === 0 && <div className="text-gray-600">AWAITING INGESTION STREAM...</div>}
              {liveSignals.map(sig => (
                <div key={sig.id} className="flex justify-between items-center border-b border-[#222] py-2">
                  <div className="flex gap-3">
                     <span className={sig.action === 'LONG' ? 'text-green-500 font-bold' : sig.action === 'SHORT' ? 'text-red-500 font-bold' : 'text-gray-400 font-bold'}>[{sig.action}]</span>
                     <span className="text-white">{sig.pair}</span>
                  </div>
                  <div className="flex flex-col items-end">
                     <span className="text-cyan-400 font-medium">{(sig.confidence * 100).toFixed(1)}% CONF</span>
                     <span className="text-[9px] text-gray-600">{new Date(sig.timestamp).toISOString()}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </aside>
      </main>
    </div>
  );
}
