import type {Metadata} from 'next';
import Link from 'next/link';
import './globals.css'; // Global styles

export const metadata: Metadata = {
  title: 'MoStar Sovereign Data Conduit',
  description: 'High-fidelity Synthetic Data Generation Platform with strict data sovereignty.',
};

export default function RootLayout({children}: {children: React.ReactNode}) {
  return (
    <html lang="en">
      <head>
        <script
          suppressHydrationWarning
          dangerouslySetInnerHTML={{
            __html: `
              try {
                if (typeof window !== 'undefined') {
                  const getPropDesc = (obj, prop) => {
                    while (obj) {
                      const desc = Object.getOwnPropertyDescriptor(obj, prop);
                      if (desc) return desc;
                      obj = Object.getPrototypeOf(obj);
                    }
                  };
                  const desc = getPropDesc(window, 'fetch');
                  if (desc && !desc.set) {
                    let fetchRef = desc.value || desc.get?.call(window);
                    Object.defineProperty(window, 'fetch', {
                      configurable: true,
                      enumerable: true,
                      get: () => fetchRef,
                      set: (val) => { fetchRef = val; }
                    });
                  }
                }
              } catch (e) {
                console.error('Fetch patch error:', e);
              }
            `
          }}
        />
      </head>
      <body className="bg-[#050505] text-white flex flex-col min-h-screen font-sans" suppressHydrationWarning>
        <header className="border-b border-[#222] px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-8">
            <div className="text-2xl font-black tracking-tighter italic">MoStar</div>
            <nav className="flex gap-6 text-xs font-bold uppercase tracking-widest text-gray-500">
              <Link href="/" className="hover:text-white transition-colors">
                Ingestion Node
              </Link>
              <Link href="/training" className="hover:text-white transition-colors">
                Training
              </Link>
              <Link href="/observer" className="hover:text-white transition-colors">
                Observer
              </Link>
              <Link href="/live-engine" className="hover:text-white transition-colors text-cyan-400">
                Live Terminal
              </Link>
            </nav>
          </div>
          <div className="flex items-center gap-4">
             <div className="bg-[#111] px-3 py-1 rounded border border-[#333] text-[10px] font-mono text-cyan-400">
               NODE: SECURE
             </div>
             <div className="flex items-center gap-2 hidden sm:flex">
               <span className="text-xs font-bold text-gray-400">DEV:</span>
               <span className="text-xs font-black bg-white text-black px-2 py-0.5 uppercase">ALEX RIVERA</span>
             </div>
          </div>
        </header>
        <div className="flex-1 overflow-auto flex flex-col">
          {children}
        </div>
        <footer className="h-8 bg-[#111] border-t border-[#222] px-6 flex items-center justify-between text-[10px] font-mono text-gray-500 shrink-0">
          <div className="flex gap-4">
            <span>SENSORS: OK</span>
            <span className="text-green-500">LATENCY: 12ms</span>
          </div>
          <div>SYNCED WITH NEURAL NETWORK CLUSTER [AFR-1]</div>
        </footer>
      </body>
    </html>
  );
}
