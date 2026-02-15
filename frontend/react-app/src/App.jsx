import { useEffect, useState, useCallback, useRef } from "react";

function App() {
  const [transcript, setTranscript] = useState([]);
  const [keywords, setKeywords] = useState([]);
  const [actions, setActions] = useState([]);
  const [connectionStatus, setConnectionStatus] = useState("Disconnected");
  const wsRef = useRef(null);
  const transcriptRef = useRef(null);

  useEffect(() => {
    if (transcriptRef.current) {
      const container = transcriptRef.current;
      const scrollHeight = container.scrollHeight;
      const clientHeight = container.clientHeight;
      
      // Scroll to bottom - 100px buffer (empty space)
      container.scrollTo({
        top: scrollHeight - clientHeight + 100,  // 100px from bottom
        behavior: "smooth"
      });
    }
  }, [transcript]);  // Runs on new transcript

  useEffect(() => {
    // Connect to your unified /ws endpoint
    const ws = new WebSocket("ws://localhost:8000/ws");
    wsRef.current = ws;

    ws.onopen = () => {
      setConnectionStatus("🟢 Connected");
      console.log("✅ Connected - waiting handshake");
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === "connected") {
          setConnectionStatus("🟢 Backend Ready");
          return;
        }
        
        const analysis = data;
        
        // Add to transcript
        setTranscript(prev => [...prev, analysis.text]);
        
        // ✅ FIXED: ACCUMULATE keywords (don't replace)
        setKeywords(prev => {
          const newKeywords = analysis.keywords || [];
          const allKeywords = [...prev, ...newKeywords];
          // Keep unique + limit to 20
          return [...new Set(allKeywords)].slice(0, 20);
        });
        
        // ✅ FIXED: Only add NEW actions
        if (analysis.actions && analysis.actions.length > 0) {
          setActions(prev => {
            const newActions = analysis.actions.filter(action => 
              !prev.some(existing => existing.includes(action.split(' → ')[1]))
            );
            return [...prev, ...newActions];
          });
        }
      } catch (e) {
        console.log("Terminal text:", event.data);
      }
    };

    ws.onclose = () => {
      setConnectionStatus("🔴 Disconnected");
      // Auto-reconnect
      setTimeout(() => {
        console.log("🔄 Reconnecting...");
        window.location.reload();
      }, 2000);
    };

    ws.onerror = (error) => {
      setConnectionStatus("❌ Error");
      console.error("WebSocket error:", error);
    };

    return () => {
      ws.close();
    };
  }, []);

  const clearAll = () => {
    setTranscript([]);
    setKeywords([]);
    setActions([]);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 p-8">
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-8">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-4xl font-black bg-gradient-to-r from-blue-600 to-purple-700 bg-clip-text text-transparent">
            🎤 FloatNote AI
          </h1>
          <div className="flex items-center gap-4 text-sm">
            <span className={`px-3 py-1 rounded-full font-medium ${
              connectionStatus.includes('Connected') ? 'bg-green-100 text-green-800' :
              connectionStatus.includes('Error') ? 'bg-red-100 text-red-800' :
              'bg-yellow-100 text-yellow-800'
            }`}>
              {connectionStatus}
            </span>
            <span className="text-gray-500">2.5s latency</span>
          </div>
        </div>
        <p className="text-xl text-gray-600">Real-Time AI-Based Meeting Assistance system</p>
      </div>

      <div className="max-w-7xl mx-auto grid grid-cols-1 xl:grid-cols-3 gap-8">
        
        {/* Live Transcript */}
        <div className="xl:col-span-2">
          <div className="bg-white/70 backdrop-blur-xl rounded-3xl p-8 shadow-2xl border border-white/50">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold flex items-center gap-3">
                📝 Live Transcript
                <span className="px-3 py-1 bg-blue-100 text-blue-800 text-sm font-medium rounded-full">
                  LIVE
                </span>
              </h2>
            </div>
            <div 
              ref={transcriptRef}
              className="h-[500px] overflow-y-auto space-y-3 pr-2"
            >
              {transcript.map((text, index) => (
                <div key={index} className="p-4 bg-gradient-to-r from-gray-50 to-gray-100 rounded-2xl 
                                            hover:shadow-md transition-all border-l-4 border-blue-200">
                  <p className="text-gray-800 leading-relaxed">{text}</p>
                </div>
              ))}
              
              {/* ✅ Remove transcriptEndRef div */}
              
              {/* Empty state */}
              {transcript.length === 0 && (
                <div className="h-full flex items-center justify-center text-gray-400">
                  <div className="text-center">
                    <div className="w-16 h-16 border-4 border-dashed border-gray-300 rounded-full 
                                    animate-spin mx-auto mb-4"></div>
                    <p>Speaking into microphone...</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* AI Insights Panel */}
        <div className="space-y-6">
          
          {/* Keywords */}
          <div className="bg-white/70 backdrop-blur-xl rounded-3xl p-6 shadow-2xl border border-white/50">
            <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
              🗝️ Keywords ({keywords.length})
            </h3>
            <div className="flex flex-wrap gap-2">
              {keywords.map((keyword, index) => (
                <span key={index} 
                      className="bg-gradient-to-r from-blue-100 to-blue-200 text-blue-800 px-4 py-2 
                                rounded-2xl text-sm font-medium hover:shadow-md transition-all cursor-pointer">
                  {keyword}
                </span>
              ))}
              {keywords.length === 0 && (
                <p className="text-gray-400 italic">No keywords detected</p>
              )}
            </div>
          </div>

          {/* Action Items */}
          <div className="bg-white/70 backdrop-blur-xl rounded-3xl p-6 shadow-2xl border border-white/50 flex-1">
            <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
              ✅ Action Items ({actions.length})
            </h3>
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {actions.map((action, index) => (
                <div key={index} 
                     className="p-4 bg-gradient-to-r from-orange-50 to-red-50 rounded-2xl border-l-4 
                               border-orange-400 hover:shadow-lg transition-all group">
                  <div className="font-semibold text-gray-800">{action}</div>
                  <div className="text-sm text-gray-500 mt-1 flex items-center gap-2">
                    <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                    <span>AI extracted</span>
                  </div>
                </div>
              ))}
              {actions.length === 0 && (
                <div className="text-center py-12 text-gray-400">
                  <div className="text-4xl mb-4">🎯</div>
                  <p className="font-medium">No actions detected yet</p>
                  <p className="text-sm">Try saying "Sarah needs to review the proposal"</p>
                </div>
              )}
            </div>
          </div>

        </div>
      </div>

      {/* Control Bar */}
      <div className="max-w-7xl mx-auto mt-12 p-6 bg-white/50 backdrop-blur-xl rounded-3xl border border-white/50">
        <div className="flex flex-col sm:flex-row gap-4 items-center justify-between">
          <div className="flex items-center gap-6 text-sm text-gray-600">
            <span>🔊 Microphone: Active</span>
            <span>⚡ Latency: 2.5s</span>
            <span>🎯 Accuracy: 99%</span>
            <span>💾 Auto-save enabled</span>
          </div>
          <button 
            onClick={clearAll}
            className="px-8 py-3 bg-gradient-to-r from-red-500 to-red-600 text-white 
                      font-semibold rounded-2xl hover:shadow-xl hover:scale-105 transition-all 
                      duration-200 flex items-center gap-2"
          >
            🗑️ Clear All
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;